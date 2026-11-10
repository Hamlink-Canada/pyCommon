"""Initial shared credential table."""

import sqlalchemy as sa
from alembic import op

revision = "0001_node_credentials"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "node_credentials",
        sa.Column("node_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("password", sa.String(79), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint(
            "node_id > 0 AND node_id <= 9223372036854775807", name="positive_node_id"
        ),
        sa.CheckConstraint("length(password) BETWEEN 1 AND 79", name="password_length"),
        sa.PrimaryKeyConstraint("node_id"),
    )


def downgrade():
    op.drop_table("node_credentials")
