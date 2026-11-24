"""Test fixtures: a temporary database and a fake AI service (no API keys or network needed)."""
import json
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config  # noqa: E402


class FakeRag:
    ready = True
    hybrid = False

    def __init__(self):
        self.calls = []

    def stream(self, question, history, mode="chat"):
        self.calls.append((question, list(history), mode))
        yield ("sources", [{"title": "Test Book", "page": 12, "snippet": "snippet"}])
        answer = f"**Answer** ({mode}) to: {question} [history={len(history)}] <script>x</script>"
        for i in range(0, len(answer), 10):
            yield ("token", answer[i:i + 10])
        yield ("done", {"answer": answer, "followups": ["Follow 1?", "Follow 2?"],
                        "sources": [{"title": "Test Book", "page": 12, "snippet": "snippet"}],
                        "usage": {"model": "fake", "input": 100, "output": 50}})

    def stream_lab_report(self, *, text=None, image_b64=None, mime=None, note=""):
        yield ("sources", [])
        yield ("token", "Your hemoglobin is normal.")
        yield ("done", {"answer": "Your hemoglobin is normal.", "followups": [], "sources": [],
                        "usage": {"model": "fake", "input": 10, "output": 5}})


@pytest.fixture()
def app(monkeypatch):
    tmp = tempfile.mkdtemp()

    class TestConfig(Config):
        DATABASE_URL = "sqlite:///" + os.path.join(tmp, "test.db").replace("\\", "/")
        RATELIMIT_CHAT = "1000 per minute"
        RATELIMIT_AUTH = "1000 per minute"
        RATELIMIT_UPLOAD = "1000 per minute"
        MODERATION_ENABLED = False
        ADMIN_EMAILS = ["admin@example.com"]
        TESTING = True

    from app import create_app
    from src.security import limiter

    application = create_app(TestConfig, warm_up=False)
    application.extensions["rag"] = FakeRag()
    limiter.reset()
    yield application


def make_client(app):
    c = app.test_client()
    r = c.get("/")
    token = re.search(r'name="csrf-token" content="([^"]+)"', r.text).group(1)
    c.csrf = token
    return c


@pytest.fixture()
def client(app):
    return make_client(app)


def post_json(c, url, body):
    return c.post(url, json=body, headers={"X-CSRF-Token": c.csrf})


def chat(c, message, **extra):
    """Send a chat message and return the parsed NDJSON events."""
    r = post_json(c, "/api/chat", {"message": message, **extra})
    if r.status_code != 200:
        return r, []
    return r, [json.loads(line) for line in r.get_data(as_text=True).splitlines() if line.strip()]


def refresh_csrf(c):
    r = c.get("/")
    c.csrf = re.search(r'name="csrf-token" content="([^"]+)"', r.text).group(1)
