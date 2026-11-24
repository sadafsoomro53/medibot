"""Database models (SQLAlchemy 2.0). Schema changes are managed by Alembic (see migrations/)."""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    create_engine,
    event,
    inspect,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    scoped_session,
    sessionmaker,
)

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:  # SQLite returns naive datetimes; we always store UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def owner_key(self) -> str:
        return f"u:{self.id}"

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name or self.email.split("@")[0],
                "is_admin": self.is_admin}


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    # Owner key: "u:<user id>" for accounts, or the anonymous browser id.
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False, default="New chat")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="chat")  # chat | symptom | labs
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )

    __table_args__ = (Index("ix_conv_user_updated", "user_id", "updated_at"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "shared": bool(self.share_token),
            "share_token": self.share_token,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text)
    followups_json: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)  # -1, 0, 1
    emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    @property
    def sources(self) -> list:
        return json.loads(self.sources_json) if self.sources_json else []

    @property
    def followups(self) -> list:
        return json.loads(self.followups_json) if self.followups_json else []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "followups": self.followups,
            "feedback": self.feedback,
            "emergency": self.emergency,
            "created_at": _iso(self.created_at),
        }


class AnswerCache(Base):
    __tablename__ = "answer_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of normalised question
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text)
    followups_json: Mapped[str | None] = mapped_column(Text)
    hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageLog(Base):
    __tablename__ = "usage_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # chat | labs | cache
    model: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


Session = scoped_session(sessionmaker(expire_on_commit=False))


def _run_migrations(engine) -> None:
    """Bring the schema up to date with Alembic (adopts databases created before Alembic)."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = AlembicConfig(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "migrations"))

    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = inspect(conn).get_table_names()
        if "conversations" in tables and "alembic_version" not in tables:
            log.info("Existing database without migration history: stamping baseline 0001")
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")


def init_db(database_url: str, migrate: bool = True) -> None:
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        path = database_url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800)

    engine = create_engine(database_url, **kwargs)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    if migrate:
        _run_migrations(engine)
    else:
        Base.metadata.create_all(engine)
    Session.configure(bind=engine)
