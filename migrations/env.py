from alembic import context
from sqlalchemy import create_engine

from src.models import Base

target_metadata = Base.metadata


def _run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite needs batch ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:  # called from the app (src.models.init_db)
    _run(connection)
else:  # called from the `alembic` CLI
    from src.config import Config

    with create_engine(Config.DATABASE_URL).connect() as conn:
        _run(conn)
        conn.commit()
