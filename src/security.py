"""Security helpers: identity (account or anonymous), CSRF protection, security headers, rate limits."""
import hmac
import secrets

from flask import abort, g, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

CSRF_HEADER = "X-CSRF-Token"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Strict CSP: only our own scripts/styles, no inline JS, no framing.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "media-src 'self' blob:",
        "worker-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self' https://accounts.google.com",
        "frame-ancestors 'none'",
    ]
)


# --------------------------------------------------------------------------- identity
def current_user():
    """The logged-in User, or None. Cached per request."""
    if "user" not in g:
        g.user = None
        uid = session.get("account_id")
        if uid:
            from src.models import Session, User

            user = Session.get(User, uid)
            # Invalidate the session if the account was removed.
            if user is None:
                session.pop("account_id", None)
            g.user = user
    return g.user


def anon_id() -> str:
    uid = session.get("uid")
    if not uid:
        uid = secrets.token_hex(16)
        session["uid"] = uid
        session.permanent = True
    return uid


def current_user_id() -> str:
    """Owner key for conversations: 'u:<id>' when logged in, otherwise the anonymous browser id."""
    user = current_user()
    return user.owner_key if user else anon_id()


def login_session(user) -> None:
    """Start a fresh session for `user` (prevents session fixation) and keep the CSRF token valid."""
    previous_anon = session.get("uid")
    session.clear()
    session["account_id"] = user.id
    session["uid"] = previous_anon or secrets.token_hex(16)
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = True
    g.user = user


def logout_session() -> None:
    session.clear()
    g.user = None


def require_admin():
    user = current_user()
    if not user or not user.is_admin:
        abort(404)
    return user


# --------------------------------------------------------------------------- CSRF
def csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def verify_csrf() -> None:
    if request.method not in _UNSAFE_METHODS:
        return
    expected = session.get("csrf")
    sent = request.headers.get(CSRF_HEADER) or request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, sent):
        abort(403, description="Invalid or missing CSRF token. Reload the page.")


# --------------------------------------------------------------------------- headers
def apply_security_headers(response):
    h = response.headers
    h.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
    if request.is_secure:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith(("/api/", "/auth/", "/admin")):
        h["Cache-Control"] = "no-store"
    h.pop("Server", None)
    return response
