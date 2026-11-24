"""Admin dashboard (accounts whose email is in ADMIN_EMAILS). Everyone else gets a 404."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template
from sqlalchemy import func, select

from src.models import AnswerCache, Conversation, Message, Session, UsageLog, User
from src.security import csrf_token, require_admin

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@bp.get("/")
def dashboard():
    admin = require_admin()
    cfg = current_app.config
    now = datetime.now(timezone.utc)
    since14 = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    since30 = now - timedelta(days=30)

    scalar = Session.scalar
    totals = {
        "users": scalar(select(func.count()).select_from(User)),
        "conversations": scalar(select(func.count()).select_from(Conversation)),
        "answers": scalar(select(func.count()).where(Message.role == "assistant")),
        "active7": scalar(select(func.count(func.distinct(Conversation.user_id)))
                          .where(Conversation.updated_at >= now - timedelta(days=7))),
        "up": scalar(select(func.count()).where(Message.feedback == 1)),
        "down": scalar(select(func.count()).where(Message.feedback == -1)),
        "emergencies": scalar(select(func.count()).where(Message.role == "user", Message.emergency.is_(True))),
        "cache_hits": scalar(select(func.coalesce(func.sum(AnswerCache.hits), 0))),
        "shared": scalar(select(func.count()).where(Conversation.share_token.is_not(None))),
    }
    rated = totals["up"] + totals["down"]
    totals["satisfaction"] = round(100 * totals["up"] / rated) if rated else None

    tin, tout = Session.execute(
        select(func.coalesce(func.sum(UsageLog.input_tokens), 0), func.coalesce(func.sum(UsageLog.output_tokens), 0))
        .where(UsageLog.created_at >= since30)
    ).one()
    cost30 = tin / 1e6 * cfg["PRICE_INPUT_PER_M"] + tout / 1e6 * cfg["PRICE_OUTPUT_PER_M"]

    day = func.date(Message.created_at)
    per_day_rows = dict(Session.execute(
        select(day, func.count()).where(Message.role == "assistant", Message.created_at >= since14).group_by(day)
    ).all())
    days = []
    for i in range(14):
        d = (since14 + timedelta(days=i)).date()
        days.append({"date": d.isoformat(), "label": d.strftime("%d %b"),
                     "count": int(per_day_rows.get(d.isoformat(), per_day_rows.get(d, 0)) or 0)})
    peak = max((d["count"] for d in days), default=0)

    q = func.lower(func.trim(Message.content))
    top_questions = Session.execute(
        select(q, func.count().label("n")).where(Message.role == "user", Message.created_at >= since30)
        .group_by(q).order_by(func.count().desc()).limit(10)
    ).all()

    disliked = []
    for m in Session.scalars(select(Message).where(Message.feedback == -1).order_by(Message.id.desc()).limit(15)):
        question = Session.scalar(
            select(Message.content).where(Message.conversation_id == m.conversation_id, Message.role == "user",
                                          Message.id < m.id).order_by(Message.id.desc()).limit(1)
        )
        disliked.append({"question": question or "", "answer": m.content[:400], "at": m.created_at})

    return render_template(
        "admin.html", admin=admin.to_dict(), csrf_token=csrf_token(), totals=totals,
        tokens={"input": tin, "output": tout}, cost30=cost30, days=days, peak=peak,
        top_questions=top_questions, disliked=disliked,
        prices=(cfg["PRICE_INPUT_PER_M"], cfg["PRICE_OUTPUT_PER_M"]),
    )
