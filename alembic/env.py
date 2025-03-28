import os
import sys
from logging.config import fileConfig
from typing import Dict

from sqlalchemy import engine_from_config, pool

from alembic import context
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.db.base import Base

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Get alembic section configuration
    configuration: Dict[str, str] = dict(
        config.get_section(config.config_ini_section) or {}
    )
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
