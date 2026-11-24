"""HTTP routes: pages, the streaming chat API and supporting endpoints."""
import base64
import hashlib
import io
import json
import logging
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, Response, abort, current_app, jsonify, render_template, request,
    send_from_directory, stream_with_context,
)
from sqlalchemy import delete, func, select

from src import medicine
from src.models import AnswerCache, Conversation, Message, Session, UsageLog
from src.safety import BLOCKED_REPLY, looks_like_emergency, moderate
from src.security import csrf_token, current_user, current_user_id, limiter

log = logging.getLogger(__name__)
bp = Blueprint("main", __name__)
_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="moderation")

MODES = {"chat", "symptom"}


def _now():
    return datetime.now(timezone.utc)


def _clean_text(value, max_chars: int, field: str, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        abort(400, description=f"'{field}' must be text.")
    text = "".join(ch for ch in value if ch in "\n\t" or ch.isprintable()).strip()
    if required and not text:
        abort(400, description=f"'{field}' cannot be empty.")
    if len(text) > max_chars:
        abort(400, description=f"'{field}' is too long (max {max_chars} characters).")
    return text


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Expected a JSON object.")
    return data


def _get_owned_conversation(conv_id) -> Conversation:
    conv = Session.get(Conversation, conv_id) if isinstance(conv_id, str) and len(conv_id) <= 32 else None
    if conv is None or conv.user_id != current_user_id():
        abort(404, description="Conversation not found.")
    return conv


def _make_title(text: str) -> str:
    title = " ".join(text.split())
    return title if len(title) <= 60 else title[:57].rstrip() + "..."


def _check_conversation_quota(uid: str) -> None:
    count = Session.scalar(select(func.count()).where(Conversation.user_id == uid))
    if count >= current_app.config["MAX_CONVERSATIONS_PER_USER"]:
        abort(409, description="Too many saved chats. Delete some old ones first.")


def _cache_key(question: str, mode: str) -> str:
    cfg = current_app.config
    norm = re.sub(r"\s+", " ", question.lower()).strip().rstrip("?.! ")
    return hashlib.sha256(f"{mode}|{cfg['PINECONE_INDEX']}|{cfg['OPENAI_MODEL']}|{norm}".encode()).hexdigest()


def _line(obj) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _stream_response(gen) -> Response:
    resp = Response(stream_with_context(gen), mimetype="application/x-ndjson")
    resp.headers["X-Accel-Buffering"] = "no"  # disable proxy buffering (nginx)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _persist(conv_id, uid, title, mode, user_text, result, emergency, kind):
    """Save the user + assistant messages once an answer is complete. Returns event payload."""
    conv = Session.get(Conversation, conv_id) if conv_id else None
    if conv is None:
        conv = Conversation(user_id=uid, title=title, mode=mode)
        Session.add(conv)
    user_msg = Message(conversation=conv, role="user", content=user_text, emergency=emergency)
    bot_msg = Message(
        conversation=conv, role="assistant", content=result["answer"] or "…",
        sources_json=json.dumps(result.get("sources") or []) or None,
        followups_json=json.dumps(result.get("followups") or []) or None,
        emergency=emergency,
    )
    Session.add_all([user_msg, bot_msg])
    conv.updated_at = _now()
    usage = result.get("usage") or {}
    Session.add(UsageLog(kind=kind, model=usage.get("model", ""),
                         input_tokens=usage.get("input", 0), output_tokens=usage.get("output", 0)))
    Session.commit()
    return {"type": "done", "conversation": conv.to_dict(),
            "user_message": user_msg.to_dict(), "assistant_message": bot_msg.to_dict()}


def _moderation_gate(events, future, flags):
    """Wait for the (parallel) moderation result once retrieval is done, before any answer text.

    Blocked input gets a fixed refusal; self-harm signals raise the emergency banner.
    """
    for kind_, payload in events:
        if future is not None and kind_ == "sources":
            try:
                mod = future.result(timeout=10)
            except Exception:
                mod = {"blocked": False, "support": False}
            future = None
            if mod["support"] and not flags["emergency"]:
                flags["emergency"] = True
                yield ("meta", True)
            if mod["blocked"]:
                events.close()
                flags["blocked"] = True
                yield from _replay(BLOCKED_REPLY, [], [])
                return
        yield kind_, payload


def _run_stream(events, *, conv_id, uid, title, mode, user_text, emergency, kind, cache_key=None, moderation=None):
    """Turn RagService events into NDJSON lines and persist the result."""
    flags = {"emergency": emergency, "blocked": False}
    events = _moderation_gate(events, moderation, flags)
    yield _line({"type": "meta", "emergency": emergency})
    try:
        result = None
        for kind_, payload in events:
            if kind_ == "meta":
                yield _line({"type": "meta", "emergency": True})
            elif kind_ == "sources":
                yield _line({"type": "sources", "sources": payload})
            elif kind_ == "token":
                yield _line({"type": "token", "t": payload})
            elif kind_ == "done":
                result = payload
        if result is None:
            raise RuntimeError("stream ended without a result")
        done = _persist(conv_id, uid, title, mode, user_text, result, flags["emergency"],
                        "blocked" if flags["blocked"] else kind)
        if cache_key and result["answer"] and not flags["blocked"] and not flags["emergency"] and kind != "cache":
            Session.merge(AnswerCache(key=cache_key, question=user_text, answer=result["answer"],
                                      sources_json=json.dumps(result.get("sources") or []),
                                      followups_json=json.dumps(result.get("followups") or []),
                                      created_at=_now()))
            Session.commit()
        yield _line(done)
    except GeneratorExit:  # client went away
        Session.rollback()
        raise
    except Exception:
        log.exception("Streaming answer failed")
        Session.rollback()
        yield _line({"type": "error", "error": "The assistant is temporarily unavailable. Please try again."})


def _replay(answer: str, sources, followups):
    """Emit a stored answer as stream events (used for cached and fixed replies)."""
    yield ("sources", sources or [])
    for i in range(0, len(answer), 24):
        yield ("token", answer[i:i + 24])
    yield ("done", {"answer": answer, "sources": sources or [], "followups": followups or [],
                    "usage": {"model": "cache", "input": 0, "output": 0}})


# --------------------------------------------------------------------------- pages
@bp.get("/")
def index():
    user = current_user()
    current_user_id()
    cfg = current_app.config
    return render_template(
        "index.html",
        csrf_token=csrf_token(),
        max_chars=cfg["MAX_MESSAGE_CHARS"],
        user=user.to_dict() if user else None,
        google_enabled=bool(cfg.get("GOOGLE_CLIENT_ID") and cfg.get("GOOGLE_CLIENT_SECRET")),
        emergency_numbers=json.dumps(cfg["EMERGENCY_NUMBERS"]),
    )


@bp.get("/share/<token>")
def shared(token):
    conv = Session.scalar(select(Conversation).where(Conversation.share_token == token)) \
        if re.fullmatch(r"[A-Za-z0-9_\-]{10,32}", token or "") else None
    if conv is None:
        abort(404)
    payload = {"conversation": {"title": conv.title, "created_at": conv.to_dict()["created_at"]},
               "messages": [m.to_dict() for m in conv.messages]}
    # `tojson` in the template escapes <, >, & and ' so message text can't break out of the data block.
    return render_template("share.html", title=conv.title, data=payload)


@bp.get("/healthz")
@limiter.exempt
def healthz():
    Session.execute(select(1))
    rag = current_app.extensions["rag"]
    return jsonify(status="ok", ai_ready=rag.ready, hybrid=getattr(rag, "hybrid", False))


# PWA files must be served from the site root to control the whole app.
@bp.get("/sw.js")
@limiter.exempt
def service_worker():
    resp = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.get("/manifest.webmanifest")
@limiter.exempt
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.webmanifest",
                               mimetype="application/manifest+json")


@bp.get("/offline")
@limiter.exempt
def offline():
    return render_template("offline.html")


# --------------------------------------------------------------------------- conversations
@bp.get("/api/conversations")
def list_conversations():
    rows = Session.scalars(
        select(Conversation).where(Conversation.user_id == current_user_id())
        .order_by(Conversation.updated_at.desc()).limit(200)
    ).all()
    return jsonify(conversations=[c.to_dict() for c in rows])


@bp.get("/api/conversations/<conv_id>")
def get_conversation(conv_id):
    conv = _get_owned_conversation(conv_id)
    return jsonify(conversation=conv.to_dict(), messages=[m.to_dict() for m in conv.messages])


@bp.patch("/api/conversations/<conv_id>")
def rename_conversation(conv_id):
    conv = _get_owned_conversation(conv_id)
    conv.title = _clean_text(_json_body().get("title"), 120, "title")
    Session.commit()
    return jsonify(conversation=conv.to_dict())


@bp.delete("/api/conversations/<conv_id>")
def delete_conversation(conv_id):
    Session.delete(_get_owned_conversation(conv_id))
    Session.commit()
    return jsonify(ok=True)


@bp.delete("/api/conversations")
def delete_all_conversations():
    uid = current_user_id()
    ids = select(Conversation.id).where(Conversation.user_id == uid)
    Session.execute(delete(Message).where(Message.conversation_id.in_(ids)))
    Session.execute(delete(Conversation).where(Conversation.user_id == uid))
    Session.commit()
    return jsonify(ok=True)


@bp.post("/api/conversations/<conv_id>/share")
def share_conversation(conv_id):
    conv = _get_owned_conversation(conv_id)
    if not conv.share_token:
        conv.share_token = secrets.token_urlsafe(16)
        Session.commit()
    return jsonify(conversation=conv.to_dict(), url=request.host_url.rstrip("/") + "/share/" + conv.share_token)


@bp.delete("/api/conversations/<conv_id>/share")
def unshare_conversation(conv_id):
    conv = _get_owned_conversation(conv_id)
    conv.share_token = None
    Session.commit()
    return jsonify(conversation=conv.to_dict())


@bp.post("/api/messages/<int:msg_id>/feedback")
def feedback(msg_id):
    msg = Session.get(Message, msg_id)
    if msg is None or msg.role != "assistant" or msg.conversation.user_id != current_user_id():
        abort(404, description="Message not found.")
    value = _json_body().get("value")
    if value not in (-1, 0, 1):
        abort(400, description="'value' must be -1, 0 or 1.")
    msg.feedback = value
    Session.commit()
    return jsonify(ok=True, feedback=value)


# --------------------------------------------------------------------------- chat (streaming)
@bp.post("/api/chat")
@limiter.limit(lambda: current_app.config["RATELIMIT_CHAT"])
def chat():
    cfg = current_app.config
    data = _json_body()
    question = _clean_text(data.get("message"), cfg["MAX_MESSAGE_CHARS"], "message")
    uid = current_user_id()

    conv_id = data.get("conversation_id")
    if conv_id:
        conv = _get_owned_conversation(conv_id)
        mode = conv.mode if conv.mode in MODES else "chat"
        recent = Session.scalars(
            select(Message).where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc()).limit(cfg["HISTORY_TURNS_FOR_CONTEXT"] * 2)
        ).all()
        history = [(m.role, m.content) for m in reversed(recent)]
        conv_id, title = conv.id, conv.title
    else:
        _check_conversation_quota(uid)
        mode = data.get("mode") if data.get("mode") in MODES else "chat"
        history, title = [], _make_title(question)
        if mode == "symptom":
            title = "Symptom check: " + _make_title(question)[:45]
    Session.commit()  # release the DB connection before slow calls

    emergency = looks_like_emergency(question)
    # Moderation runs in parallel with retrieval; the answer waits for it (see _moderation_gate).
    moderation = _pool.submit(moderate, question, cfg["OPENAI_API_KEY"]) if cfg["MODERATION_ENABLED"] else None
    common = dict(conv_id=conv_id, uid=uid, title=title, mode=mode, user_text=question,
                  emergency=emergency, moderation=moderation)

    cache_key = None
    if not history and mode == "chat" and not emergency and cfg["ANSWER_CACHE_HOURS"] > 0:
        cache_key = _cache_key(question, mode)
        hit = Session.get(AnswerCache, cache_key)
        if hit:
            created = hit.created_at if hit.created_at.tzinfo else hit.created_at.replace(tzinfo=timezone.utc)
            if _now() - created < timedelta(hours=cfg["ANSWER_CACHE_HOURS"]):
                hit.hits += 1
                Session.commit()
                events = _replay(hit.answer, json.loads(hit.sources_json or "[]"),
                                 json.loads(hit.followups_json or "[]"))
                return _stream_response(_run_stream(events, kind="cache", **common))

    events = current_app.extensions["rag"].stream(question, history, mode)
    return _stream_response(_run_stream(events, kind="chat", cache_key=cache_key, **common))


# --------------------------------------------------------------------------- lab reports
_IMAGE_MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}


@bp.post("/api/labs")
@limiter.limit(lambda: current_app.config["RATELIMIT_UPLOAD"])
def lab_report():
    cfg = current_app.config
    request.max_content_length = cfg["MAX_UPLOAD_BYTES"] + 64 * 1024
    file = request.files.get("file")
    if not file or not file.filename:
        abort(400, description="Please choose a PDF or image file.")
    raw = file.read(cfg["MAX_UPLOAD_BYTES"] + 1)
    if len(raw) > cfg["MAX_UPLOAD_BYTES"]:
        abort(413, description="File is too large (max 5 MB).")
    note = _clean_text(request.form.get("note"), 500, "note", required=False)
    filename = re.sub(r"[^\w.\- ]", "", file.filename)[:80] or "report"

    rag = current_app.extensions["rag"]
    if raw.startswith(b"%PDF"):
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:10]).strip()
        except Exception:
            abort(400, description="Couldn't read this PDF. Try a photo or screenshot of the report instead.")
        if len(text) < 30:
            abort(400, description="This PDF looks like a scan with no text. Please upload it as an image (photo/screenshot).")
        events = rag.stream_lab_report(text=text[:12000], note=note)
    else:
        mime = next((m for magic, m in _IMAGE_MAGIC.items() if raw.startswith(magic)), None)
        if mime == "image/webp" and raw[8:12] != b"WEBP":
            mime = None
        if not mime:
            abort(400, description="Unsupported file. Upload a PDF, PNG, JPG or WEBP.")
        events = rag.stream_lab_report(image_b64=base64.b64encode(raw).decode(), mime=mime, note=note)

    uid = current_user_id()
    conv_id = request.form.get("conversation_id") or None
    if conv_id:
        conv = _get_owned_conversation(conv_id)
        conv_id, title = conv.id, conv.title
    else:
        _check_conversation_quota(uid)
        title = "Lab report: " + filename[:45]
    Session.commit()

    user_text = f"📎 {filename}" + (f"\n{note}" if note else "")
    return _stream_response(_run_stream(events, conv_id=conv_id, uid=uid, title=title, mode="labs",
                                        user_text=user_text, emergency=False, kind="labs"))


# --------------------------------------------------------------------------- medicine lookup
@bp.get("/api/medicine")
@limiter.limit("30 per minute")
def medicine_lookup():
    q = _clean_text(request.args.get("q"), 60, "q")
    try:
        result = medicine.lookup(q)
    except Exception:
        abort(503, description="The medicine database is not reachable right now. Please try again later.")
    if not result:
        abort(404, description=f"No information found for “{q}”. Try the generic name (e.g. ibuprofen).")
    return jsonify(medicine=result)
