"""Accounts, sharing, modes, sources, feedback, answer cache and usage log.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("google_sub", sa.String(64), unique=True),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    with op.batch_alter_table("conversations") as b:
        b.add_column(sa.Column("mode", sa.String(16), nullable=False, server_default="chat"))
        b.add_column(sa.Column("share_token", sa.String(32)))
        b.create_unique_constraint("uq_conversations_share_token", ["share_token"])
    with op.batch_alter_table("messages") as b:
        b.add_column(sa.Column("sources_json", sa.Text))
        b.add_column(sa.Column("followups_json", sa.Text))
        b.add_column(sa.Column("feedback", sa.SmallInteger, nullable=False, server_default="0"))
        b.add_column(sa.Column("emergency", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table(
        "answer_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("sources_json", sa.Text),
        sa.Column("followups_json", sa.Text),
        sa.Column("hits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "usage_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("model", sa.String(40), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_usage_log_created_at", "usage_log", ["created_at"])


def downgrade():
    op.drop_table("usage_log")
    op.drop_table("answer_cache")
    with op.batch_alter_table("messages") as b:
        for col in ("emergency", "feedback", "followups_json", "sources_json"):
            b.drop_column(col)
    with op.batch_alter_table("conversations") as b:
        b.drop_constraint("uq_conversations_share_token", type_="unique")
        b.drop_column("share_token")
        b.drop_column("mode")
    op.drop_table("users")
