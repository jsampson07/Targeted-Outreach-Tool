"""ORM models package.

Import from submodules (e.g. ``from app.models.user import User``).
Table registration for Alembic lives in ``app.db.base`` — keep this
package ``__init__`` free of eager model imports so we don't cycle with
``base.py`` (model module → Base → model module).
"""
