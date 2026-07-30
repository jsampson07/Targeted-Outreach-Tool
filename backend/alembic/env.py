from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import every model so Base.metadata is fully populated for Alembic
# autogenerate (DATA_MODEL.md §3.3). Kept here — not in app.db.base —
# to avoid a circular import with model modules that import Base.
from app.models.user import User  # noqa: E402, F401
from app.models.company import Company  # noqa: E402, F401
from app.models.resume import Resume  # noqa: E402, F401
from app.models.refresh_token import RefreshToken  # noqa: E402, F401
from app.models.job_description import JobDescription  # noqa: E402, F401
from app.models.raw_provider_result import RawProviderResult  # noqa: E402, F401
from app.models.contact import Contact  # noqa: E402, F401
from app.models.generated_email import GeneratedEmail  # noqa: E402, F401
from app.models.outcome import Outcome  # noqa: E402, F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATA_MODEL.md §3.3: target_metadata = Base.metadata, with every model
# imported above so autogenerate can see all tables.
target_metadata = Base.metadata

# Override alembic.ini's empty sqlalchemy.url with settings (never hardcode).
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
