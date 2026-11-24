"""Accounts: email/password sign-up and login, optional Google sign-in.

When someone logs in, the chats they made anonymously in that browser move to their account,
so history then follows them to any device.
"""
import hmac
import logging
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, current_app, jsonify, redirect, request, session, url_for
from sqlalchemy import func, select, update
from werkzeug.security import check_password_hash, generate_password_hash

from src.models import Conversation, Session, User
from src.security import anon_id, current_user, limiter, login_session, logout_session

log = logging.getLogger(__name__)
bp = Blueprint("auth", __name__, url_prefix="/auth")

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[a-zA-Z]{2,}$")
# A real hash to compare against when the email doesn't exist (keeps response time constant).
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


def _now():
    return datetime.now(timezone.utc)


def _json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Expected a JSON object.")
    return data


def _is_admin_email(email: str) -> bool:
    return email.lower() in current_app.config["ADMIN_EMAILS"]


def _adopt_anonymous_chats(user: User) -> None:
    """Move chats created anonymously in this browser to the account."""
    anon = session.get("uid")
    if anon:
        Session.execute(
            update(Conversation).where(Conversation.user_id == anon).values(user_id=user.owner_key)
        )


def _finish_login(user: User) -> None:
    user.last_login_at = _now()
    if _is_admin_email(user.email):
        user.is_admin = True
    anon_id()
    _adopt_anonymous_chats(user)
    Session.commit()
    login_session(user)


def _google_enabled() -> bool:
    cfg = current_app.config
    return bool(cfg.get("GOOGLE_CLIENT_ID") and cfg.get("GOOGLE_CLIENT_SECRET"))


# --------------------------------------------------------------------------- endpoints
@bp.get("/me")
def me():
    user = current_user()
    return jsonify(user=user.to_dict() if user else None, google=_google_enabled())


@bp.post("/signup")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def signup():
    data = _json()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    name = " ".join(str(data.get("name", "")).split())[:80]

    if not _EMAIL_RE.match(email) or len(email) > 254:
        abort(400, description="Please enter a valid email address.")
    if len(password) < 8 or len(password) > 128:
        abort(400, description="Password must be 8–128 characters.")
    if password.lower() == password or not re.search(r"\d", password):
        abort(400, description="Use at least one capital letter and one number in your password.")
    if Session.scalar(select(func.count()).where(User.email == email)):
        abort(409, description="An account with this email already exists. Please log in.")

    user = User(email=email, name=name, password_hash=generate_password_hash(password))
    Session.add(user)
    Session.flush()
    _finish_login(user)
    return jsonify(user=user.to_dict())


@bp.post("/login")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def login():
    data = _json()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = Session.scalar(select(User).where(User.email == email)) if email else None

    ok = check_password_hash(user.password_hash if user and user.password_hash else _DUMMY_HASH, password)
    if not user or not user.password_hash or not ok:
        abort(401, description="Incorrect email or password.")
    _finish_login(user)
    return jsonify(user=user.to_dict())


@bp.post("/logout")
def logout():
    logout_session()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- Google sign-in (optional)
def _redirect_uri() -> str:
    base = current_app.config["PUBLIC_BASE_URL"] or request.host_url.rstrip("/")
    return base + url_for("auth.google_callback")


@bp.get("/google")
def google_start():
    if not _google_enabled():
        abort(404)
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@bp.get("/google/callback")
def google_callback():
    if not _google_enabled():
        abort(404)
    expected = session.pop("oauth_state", None)
    if not expected or not hmac.compare_digest(expected, request.args.get("state", "")):
        abort(400, description="Sign-in expired. Please try again.")
    code = request.args.get("code")
    if not code:
        return redirect("/")
    cfg = current_app.config
    try:
        token = requests.post("https://oauth2.googleapis.com/token", timeout=10, data={
            "code": code, "client_id": cfg["GOOGLE_CLIENT_ID"], "client_secret": cfg["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": _redirect_uri(), "grant_type": "authorization_code",
        }).json()
        info = requests.get("https://openidconnect.googleapis.com/v1/userinfo", timeout=10,
                            headers={"Authorization": f"Bearer {token['access_token']}"}).json()
    except Exception:
        log.exception("Google sign-in failed")
        abort(502, description="Google sign-in failed. Please try again.")
    if not info.get("email_verified") or not info.get("email"):
        abort(400, description="Your Google email address is not verified.")

    email = info["email"].lower()
    user = Session.scalar(select(User).where(User.google_sub == info["sub"])) or \
        Session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=info.get("name", "")[:80], google_sub=info["sub"])
        Session.add(user)
        Session.flush()
    elif not user.google_sub:
        user.google_sub = info["sub"]
    _finish_login(user)
    return redirect("/")
