import io
import json

from src.rag import FollowupSplitter
from src.safety import looks_like_emergency
from tests.conftest import chat, make_client, post_json, refresh_csrf


# --------------------------------------------------------------------------- pages & headers
def test_index_has_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_healthz_and_pwa_files(client):
    assert client.get("/healthz").get_json()["status"] == "ok"
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["Service-Worker-Allowed"] == "/"
    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/offline").status_code == 200


# --------------------------------------------------------------------------- chat
def test_csrf_required(client):
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 403


def test_validation(client):
    assert post_json(client, "/api/chat", {"message": "   "}).status_code == 400
    assert post_json(client, "/api/chat", {"message": "x" * 1001}).status_code == 400
    assert post_json(client, "/api/chat", {"message": 5}).status_code == 400


def test_streaming_chat_saves_history_sources_and_followups(client, app):
    r, events = chat(client, "What is diabetes?")
    assert r.mimetype == "application/x-ndjson"
    types = [e["type"] for e in events]
    assert types[0] == "meta" and types[1] == "sources" and types[-1] == "done"
    streamed = "".join(e["t"] for e in events if e["type"] == "token")
    done = events[-1]
    assert done["assistant_message"]["content"] == streamed
    assert done["assistant_message"]["sources"][0]["page"] == 12
    assert done["assistant_message"]["followups"] == ["Follow 1?", "Follow 2?"]

    conv_id = done["conversation"]["id"]
    _, events2 = chat(client, "What are its symptoms?", conversation_id=conv_id)
    assert "[history=2]" in events2[-1]["assistant_message"]["content"]
    msgs = client.get(f"/api/conversations/{conv_id}").get_json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]


def test_answer_cache(client, app):
    rag = app.extensions["rag"]
    chat(client, "What is asthma?")
    chat(client, "what is ASTHMA")  # same question, different case -> cached
    assert len(rag.calls) == 1


def test_symptom_mode(client, app):
    _, events = chat(client, "I want to check my symptoms", mode="symptom")
    conv = events[-1]["conversation"]
    assert conv["mode"] == "symptom" and conv["title"].startswith("Symptom check")
    _, events2 = chat(client, "headache for 3 days", conversation_id=conv["id"])
    assert "(symptom)" in events2[-1]["assistant_message"]["content"]


def test_emergency_flag(client):
    _, events = chat(client, "My father has severe chest pain right now")
    assert events[0] == {"type": "meta", "emergency": True}
    assert events[-1]["user_message"]["emergency"] is True


def test_moderation_blocks_and_flags(client, app, monkeypatch):
    from src import routes
    from src.safety import BLOCKED_REPLY

    app.config["MODERATION_ENABLED"] = True
    monkeypatch.setattr(routes, "moderate", lambda text, key: {"blocked": "bad" in text, "support": "sad" in text})
    _, events = chat(client, "something bad")
    assert events[-1]["assistant_message"]["content"] == BLOCKED_REPLY
    assert "Answer" not in "".join(e.get("t", "") for e in events)  # the model's answer was never streamed

    _, events = chat(client, "I feel so sad and alone")
    assert {"type": "meta", "emergency": True} in events
    assert events[-1]["user_message"]["emergency"] is True


def test_emergency_detection_languages():
    assert looks_like_emergency("I want to end my life")
    assert looks_like_emergency("mere seene mein dard hai")
    assert looks_like_emergency("سینے میں درد ہو رہا ہے")
    assert not looks_like_emergency("What causes a mild headache?")


# --------------------------------------------------------------------------- ownership, feedback, share
def test_other_users_cannot_access(client, app):
    _, events = chat(client, "private question")
    conv_id = events[-1]["conversation"]["id"]
    msg_id = events[-1]["assistant_message"]["id"]
    other = make_client(app)
    assert other.get(f"/api/conversations/{conv_id}").status_code == 404
    assert other.delete(f"/api/conversations/{conv_id}", headers={"X-CSRF-Token": other.csrf}).status_code == 404
    assert post_json(other, f"/api/messages/{msg_id}/feedback", {"value": 1}).status_code == 404
    assert post_json(other, f"/api/conversations/{conv_id}/share", {}).status_code == 404


def test_feedback(client):
    _, events = chat(client, "q")
    msg_id = events[-1]["assistant_message"]["id"]
    assert post_json(client, f"/api/messages/{msg_id}/feedback", {"value": -1}).get_json()["feedback"] == -1
    assert post_json(client, f"/api/messages/{msg_id}/feedback", {"value": 5}).status_code == 400


def test_share_link_is_read_only_and_escaped(client, app):
    _, events = chat(client, "</script><script>alert(1)</script>")
    conv_id = events[-1]["conversation"]["id"]
    url = post_json(client, f"/api/conversations/{conv_id}/share", {}).get_json()["url"]
    token = url.rsplit("/", 1)[1]
    page = make_client(app).get(f"/share/{token}")
    assert page.status_code == 200
    assert "<script>alert(1)</script>" not in page.text  # escaped inside the JSON block
    client.delete(f"/api/conversations/{conv_id}/share", headers={"X-CSRF-Token": client.csrf})
    assert make_client(app).get(f"/share/{token}").status_code == 404


# --------------------------------------------------------------------------- accounts
def test_signup_login_and_chat_adoption(client, app):
    _, events = chat(client, "asked before signing up")
    conv_id = events[-1]["conversation"]["id"]

    weak = post_json(client, "/auth/signup", {"email": "a@example.com", "password": "short"})
    assert weak.status_code == 400
    r = post_json(client, "/auth/signup", {"email": "A@Example.com", "password": "Secret123", "name": "Ali"})
    assert r.status_code == 200 and r.get_json()["user"]["email"] == "a@example.com"
    refresh_csrf(client)
    # the anonymous chat now belongs to the account
    assert any(c["id"] == conv_id for c in client.get("/api/conversations").get_json()["conversations"])
    assert post_json(client, "/auth/signup", {"email": "a@example.com", "password": "Secret123"}).status_code == 409

    # log in from a "different device"
    device2 = make_client(app)
    assert post_json(device2, "/auth/login", {"email": "a@example.com", "password": "wrong"}).status_code == 401
    assert post_json(device2, "/auth/login", {"email": "a@example.com", "password": "Secret123"}).status_code == 200
    refresh_csrf(device2)
    assert any(c["id"] == conv_id for c in device2.get("/api/conversations").get_json()["conversations"])

    post_json(device2, "/auth/logout", {})
    refresh_csrf(device2)
    assert device2.get("/api/conversations").get_json()["conversations"] == []


def test_admin_dashboard_access(client, app):
    assert client.get("/admin").status_code == 404
    post_json(client, "/auth/signup", {"email": "admin@example.com", "password": "Admin1234"})
    refresh_csrf(client)
    chat(client, "hello")
    r = client.get("/admin")
    assert r.status_code == 200 and "Answers per day" in r.text


# --------------------------------------------------------------------------- labs & medicine
def test_lab_upload_validation_and_stream(client):
    bad = client.post("/api/labs", data={"file": (io.BytesIO(b"not a real file"), "x.txt")},
                      headers={"X-CSRF-Token": client.csrf}, content_type="multipart/form-data")
    assert bad.status_code == 400
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = client.post("/api/labs", data={"file": (io.BytesIO(png), "cbc.png"), "note": "I am 40"},
                    headers={"X-CSRF-Token": client.csrf}, content_type="multipart/form-data")
    assert r.status_code == 200
    events = [json.loads(x) for x in r.get_data(as_text=True).splitlines() if x]
    assert events[-1]["conversation"]["mode"] == "labs"
    assert events[-1]["user_message"]["content"].startswith("📎 cbc.png")


def test_lab_upload_too_large(client):
    big = b"%PDF" + b"0" * (6 * 1024 * 1024)
    r = client.post("/api/labs", data={"file": (io.BytesIO(big), "big.pdf")},
                    headers={"X-CSRF-Token": client.csrf}, content_type="multipart/form-data")
    assert r.status_code == 413


def test_medicine_lookup(client, monkeypatch):
    from src import medicine

    monkeypatch.setattr(medicine, "lookup", lambda q: {"generic": q, "sections": []} if q == "ibuprofen" else None)
    assert client.get("/api/medicine?q=ibuprofen").get_json()["medicine"]["generic"] == "ibuprofen"
    assert client.get("/api/medicine?q=zzzz").status_code == 404


# --------------------------------------------------------------------------- unit
def test_followup_splitter_hides_marker():
    s = FollowupSplitter()
    out = "".join(s.feed(tok) for tok in ["Hello ", "world.\n\n[[FOLL", "OWUPS]]\n- One?\n", "- Two?"])
    answer, followups, tail = s.finish()
    assert "[[" not in out + tail
    assert answer == "Hello world."
    assert followups == ["One?", "Two?"]
