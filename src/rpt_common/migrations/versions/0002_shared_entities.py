"""Add shared entity identities and administration assignments."""

import sqlalchemy as sa
from alembic import op

revision = "0002_shared_entities"
down_revision = "0001_node_credentials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("is_system_maintained", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "entity_type IN ('organization', 'club', 'association', 'society', 'league', "
            "'union', 'federation', 'other')",
            name="valid_entity_type",
        ),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 200", name="valid_entity_name"),
        sa.CheckConstraint(
            "(is_system_maintained = true AND owner_user_id IS NULL) OR "
            "(is_system_maintained = false AND owner_user_id IS NOT NULL)",
            name="entity_ownership_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "entity_call_signs",
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("call_sign", sa.String(length=32), nullable=False),
        sa.Column("primary_call_sign", sa.String(length=32), nullable=False),
        sa.Column("primary_is_primary", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("primary_is_primary = true", name="call_sign_points_to_primary"),
        sa.CheckConstraint(
            "(is_primary = true AND call_sign = primary_call_sign) OR "
            "(is_primary = false AND call_sign <> primary_call_sign)",
            name="call_sign_requires_primary",
        ),
        sa.CheckConstraint("length(call_sign) BETWEEN 1 AND 32", name="valid_call_sign_length"),
        sa.CheckConstraint("call_sign = upper(call_sign)", name="normalized_call_sign"),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entities.id"], name="fk_entity_call_sign_entity", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "primary_call_sign", "primary_is_primary"],
            [
                "entity_call_signs.entity_id",
                "entity_call_signs.call_sign",
                "entity_call_signs.is_primary",
            ],
            name="fk_call_sign_primary",
            deferrable=True,
            initially="DEFERRED",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id", "call_sign"),
        sa.UniqueConstraint(
            "entity_id", "call_sign", "is_primary", name="uq_entity_call_sign_primary_role"
        ),
        sa.UniqueConstraint("call_sign", name="uq_entity_call_sign_global"),
    )
    op.create_index(
        "uq_entity_one_primary_call_sign",
        "entity_call_signs",
        ["entity_id"],
        unique=True,
        sqlite_where=sa.text("is_primary = 1"),
        postgresql_where=sa.text("is_primary"),
    )
    op.create_table(
        "entity_super_admins",
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint("length(user_id) BETWEEN 1 AND 255", name="valid_admin_user_id"),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entities.id"], name="fk_entity_admin_entity", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("entity_id", "user_id"),
    )


def downgrade():
    op.drop_table("entity_super_admins")
    op.drop_index("uq_entity_one_primary_call_sign", table_name="entity_call_signs")
    op.drop_table("entity_call_signs")
    op.drop_table("entities")
