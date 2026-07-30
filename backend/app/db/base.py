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


# Model modules import Base from this file. Do NOT import models here —
# that creates a circular import whenever anything loads a model first
# (e.g. deps → User → Base → User). Alembic registers models explicitly
# in alembic/env.py so Base.metadata is complete for autogenerate.
