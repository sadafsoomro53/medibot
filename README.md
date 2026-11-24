# MediBot: AI Medical Assistant (RAG)

MediBot answers general medical questions using Retrieval-Augmented Generation: it searches trusted
medical reference books (currently *The Gale Encyclopedia of Medicine, 2nd ed.*), then asks GPT-4o to
answer **from those passages, with page citations**.

> MediBot gives general information, not medical advice or a diagnosis.

## ✨ Features

**Answers**
- **Streaming answers** that appear word by word.
- **Source citations**: every answer lists the book and page it used, with the passage.
- **Hybrid search**: keyword (BM25) + vector search (`BAAI/bge-small-en-v1.5`) on Pinecone.
- **Smart follow-ups**: "what are its symptoms?" and Urdu / Roman Urdu questions are rewritten into
  English search queries before searching.
- **Suggested follow-up questions** under each answer.
- **Answer cache**: repeated first questions are answered instantly at no API cost.

**Tools**
- **Guided symptom checker**: one question at a time, ending with which kind of doctor to see and how urgent it seems.
- **Lab report explainer**: upload a PDF or photo; each value is explained in plain language (files are not stored).
- **Medicine lookup**: uses, warnings and side effects from U.S. FDA labels (openFDA). No dosages.
- **Emergency detection**: English, Roman Urdu and Urdu. Shows a banner with tap-to-call numbers (1122, 115, …).

**Users**
- **Accounts**: email + password sign-up and login, plus optional Google sign-in. Chats made before
  logging in move into the account, so history follows the user to any device.
- **Chat history** grouped by date, with search, rename and delete.
- **👍 / 👎 feedback** on answers.
- **Share** a read-only link to a chat, or **export it as PDF**.
- **Voice**: ask by speaking, and have answers read aloud.
- **Urdu interface** with right-to-left layout, plus a light/dark theme.
- **Installable app (PWA)** with an offline page.
- Interactive animated background.

**Operations**
- **Admin dashboard** (`/admin`): usage, answers per day, satisfaction, most asked questions, 👎 answers and estimated OpenAI cost.
- **Security**: strict CSP, CSRF tokens, rate limits, input limits, OpenAI moderation, hardened system prompt,
  session-fixation protection, owner-only access to chats.
- **Scalable**: SQLite → PostgreSQL, Redis-backed rate limits, Alembic migrations, Docker Compose, `/healthz`.
- **Tests and CI**: `pytest` suite (AI faked), run on GitHub Actions for every push.
- **Optional Sentry** error tracking.

## 🚀 Quick start (local)

```bash
pip install -r requirements.txt
cp .env.example .env            # fill in PINECONE_API_KEY, OPENAI_API_KEY, SECRET_KEY (and ADMIN_EMAILS)
python store-index.py           # once: builds the knowledge base from PDFs in data/
python app.py                   # http://127.0.0.1:8080
```

Database tables are created and migrated automatically on start-up (Alembic). You can also run
`alembic upgrade head` yourself.

### Adding more books

Drop more trusted PDFs into `data/` (e.g. the other Gale volumes; the bundled file is **Volume 2, C–F**)
and run `python store-index.py` again. Chunk ids are stable, so re-running replaces existing chunks
instead of duplicating them. Use `--reset` to rebuild the index from scratch.

## 🐳 Docker (PostgreSQL + Redis)

```bash
python store-index.py            # builds instance/chunks.jsonl (mounted into the container)
docker compose up -d --build     # http://localhost:8080
docker compose up -d --scale app=3   # more app instances (put a load balancer in front)
```

## 🧪 Tests

```bash
pip install -r requirements-ci.txt   # or the full requirements.txt
python -m pytest tests -q
```

## 🔌 API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | `{message, conversation_id?, mode?}` → NDJSON stream: `meta`, `sources`, `token`…, `done` |
| `POST` | `/api/labs` | multipart `file` (PDF/PNG/JPG/WEBP ≤ 5 MB), `note?`, `conversation_id?` → same stream |
| `GET` | `/api/medicine?q=` | Medicine information (openFDA) |
| `GET` | `/api/conversations` | List your chats |
| `GET/PATCH/DELETE` | `/api/conversations/<id>` | Read / rename / delete a chat |
| `POST/DELETE` | `/api/conversations/<id>/share` | Create / revoke a read-only share link |
| `POST` | `/api/messages/<id>/feedback` | `{value: 1 \| 0 \| -1}` |
| `POST` | `/auth/signup`, `/auth/login`, `/auth/logout` | Accounts; `GET /auth/google` for Google sign-in |
| `GET` | `/healthz` | Health check |

All state-changing requests need the `X-CSRF-Token` header (from the page's `csrf-token` meta tag).

## 🏗️ Project structure

```
app.py                  App factory, error handling, server entry point
store-index.py          Builds the knowledge base (Pinecone + instance/chunks.jsonl)
src/config.py           All settings (see .env.example)
src/models.py           Users, conversations, messages, answer cache, usage log
src/rag.py              Retrieval, query rewriting, streaming, citations, follow-ups, lab reports
src/prompt.py           System prompts (chat, symptom checker, lab reports, query rewrite)
src/routes.py           Pages and the JSON / streaming API
src/auth.py             Sign-up, login, Google sign-in
src/admin.py            Admin dashboard
src/safety.py           Emergency detection and moderation
src/medicine.py         openFDA medicine lookup
src/security.py         Identity, CSRF, security headers, rate limiter
migrations/             Alembic database migrations
templates/              index, share, admin, error and offline pages
static/                 app.js, background.js, markdown.js, styles, service worker, manifest, icons
tests/                  pytest suite
Dockerfile, docker-compose.yml, .github/workflows/ci.yml
```

## 👤 Author

Sadaf Soomro · sadafsoomro53@gmail.com
