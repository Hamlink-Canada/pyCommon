"""Run only through an explicitly supplied writable connection."""

from alembic import context

from rpt_common.models.credentials import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("migrations require an explicitly supplied writable connection")
context.configure(connection=connection, target_metadata=Base.metadata)
with context.begin_transaction():
    context.run_migrations()
