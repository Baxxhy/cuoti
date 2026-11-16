"""Migration bootstrap. No baseline or schema changes have been generated."""

from alembic import context
from cuoti_backend.config import Settings
from sqlalchemy import create_engine

# Existing tables will be mapped during the later business migration stages.
target_metadata = None


def run_migrations():
    settings = Settings.load()
    if context.is_offline_mode():
        context.configure(url=settings.database_url(), target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(settings.database_url())
        try:
            with engine.connect() as connection:
                context.configure(
                    connection=connection, target_metadata=target_metadata
                )
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
