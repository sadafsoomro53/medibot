"""MediBot web app.

Run locally:      python app.py
Production:       waitress-serve --call --listen=0.0.0.0:8080 app:create_app   (Windows/Linux)
                  gunicorn -w 4 -k gthread --threads 8 -b 0.0.0.0:8080 "app:create_app()"   (Linux)
"""
import logging
import sys
from datetime import timedelta

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from src import admin, auth, routes
from src.config import Config
from src.models import Session, init_db
from src.rag import RagService
from src.security import apply_security_headers, limiter, verify_csrf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("medibot")

_JSON_PREFIXES = ("/api/", "/auth/")


def _init_sentry(dsn: str | None) -> None:
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1, send_default_pii=False)
        log.info("Sentry error tracking enabled")
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry-sdk is not installed (pip install sentry-sdk[flask])")


def create_app(config_class=Config, warm_up: bool = True) -> Flask:
    _init_sentry(config_class.SENTRY_DSN)

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=config_class.PERMANENT_SESSION_LIFETIME)

    if app.config["TRUSTED_PROXIES"]:
        n = app.config["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    init_db(app.config["DATABASE_URL"])
    limiter.init_app(app)

    rag = RagService(config_class)
    app.extensions["rag"] = rag
    if warm_up:
        rag.warm_up_async()

    app.before_request(verify_csrf)
    app.after_request(apply_security_headers)

    @app.teardown_appcontext
    def _remove_session(_exc=None):
        Session.remove()

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        if request.path.startswith(_JSON_PREFIXES) or request.is_json:
            message = err.description
            if err.code == 429:
                message = "You're sending requests too quickly. Please wait a moment."
            elif err.code == 413:
                message = "That file or message is too large."
            return jsonify(error=message), err.code
        return render_template("error.html", code=err.code, message=err.name), err.code

    @app.errorhandler(Exception)
    def _unhandled(err):
        app.logger.exception("Unhandled error")
        Session.rollback()
        if request.path.startswith(_JSON_PREFIXES):
            return jsonify(error="Something went wrong. Please try again."), 500
        return render_template("error.html", code=500, message="Server error"), 500

    app.register_blueprint(routes.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    return app


# Top-level WSGI app for Vercel (and `gunicorn app:app`). Skipped under pytest so the
# test suite can build its own app with a temporary database via create_app().
app = None if "pytest" in sys.modules else create_app()


if __name__ == "__main__":
    app = app or create_app()
    cfg = app.config
    if cfg["DEBUG"]:
        app.run(host=cfg["HOST"], port=cfg["PORT"], debug=True, use_reloader=False, threaded=True)
    else:
        from waitress import serve

        log.info("Serving on http://%s:%s", cfg["HOST"], cfg["PORT"])
        # send_bytes=1 flushes streamed answers to the browser immediately
        serve(app, host=cfg["HOST"], port=cfg["PORT"], threads=cfg["THREADS"], send_bytes=1)
