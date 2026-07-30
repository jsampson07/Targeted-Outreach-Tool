from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Exact naming convention from DATA_MODEL.md §3.2 — predictable constraint
# names so future hand-written migrations can reference them reliably.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Import every model so Base.metadata is fully populated for Alembic
# autogenerate (DATA_MODEL.md §3.3). Keep this list in dependency order
# for readability; import side-effects register tables on Base.
from app.models.user import User  # noqa: E402, F401
from app.models.company import Company  # noqa: E402, F401
from app.models.resume import Resume  # noqa: E402, F401
from app.models.refresh_token import RefreshToken  # noqa: E402, F401
from app.models.job_description import JobDescription  # noqa: E402, F401
from app.models.raw_provider_result import RawProviderResult  # noqa: E402, F401
from app.models.contact import Contact  # noqa: E402, F401
from app.models.generated_email import GeneratedEmail  # noqa: E402, F401
from app.models.outcome import Outcome  # noqa: E402, F401
