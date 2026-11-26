"""Shared cross-product entity identity and administration records."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from rpt_common.models.credentials import Base
from rpt_common.utils.regex import CALL_SIGN_RE, USER_ID_RE

ENTITY_TYPES = frozenset(
    {"organization", "club", "association", "society", "league", "union", "federation", "other"}
)


def valid_user_id(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 255
        and USER_ID_RE.fullmatch(value) is not None
    )


def valid_call_sign(value):
    return (
        isinstance(value, str)
        and 1 <= len(value.strip()) <= 32
        and value.strip().isascii()
        and CALL_SIGN_RE.fullmatch(value.strip()) is not None
    )


def normalize_call_sign(value):
    if not valid_call_sign(value):
        raise ValueError("invalid call sign")
    return value.strip().upper()


class Entity(Base):
    """A shared organization identity, independent of any one product."""

    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('organization', 'club', 'association', 'society', 'league', "
            "'union', 'federation', 'other')",
            name="valid_entity_type",
        ),
        CheckConstraint("length(name) BETWEEN 1 AND 200", name="valid_entity_name"),
        CheckConstraint(
            "(is_system_maintained = true AND owner_user_id IS NULL) OR "
            "(is_system_maintained = false AND owner_user_id IS NOT NULL)",
            name="entity_ownership_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_system_maintained: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    owner_user_id: Mapped[str | None] = mapped_column(String(255))
    call_signs: Mapped[list["EntityCallSign"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("name")
    def validate_name(self, key, value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
            raise ValueError("invalid entity name")
        return value.strip()

    @validates("entity_type")
    def validate_entity_type(self, key, value):
        if value not in ENTITY_TYPES:
            raise ValueError("invalid entity type")
        return value

    def assign_owner(self, user_id):
        """Transfer a system-maintained entity to a Keycloak user identity."""
        if not valid_user_id(user_id):
            raise ValueError("invalid owner user ID")
        self.owner_user_id = user_id
        self.is_system_maintained = False

    def return_to_system_maintained(self):
        """Clear the owner; the local admin CLI coordinates admin removal."""
        self.owner_user_id = None
        self.is_system_maintained = True

    def add_primary_call_sign(self, call_sign):
        if any(item.is_primary for item in self.call_signs):
            raise ValueError("entity already has a primary call sign")
        normalized = normalize_call_sign(call_sign)
        record = EntityCallSign(call_sign=normalized, primary_call_sign=normalized, is_primary=True)
        self.call_signs.append(record)
        return record

    def add_aka_call_sign(self, call_sign):
        primary = next((item for item in self.call_signs if item.is_primary), None)
        if primary is None:
            raise ValueError("an AKA call sign requires a primary call sign")
        normalized = normalize_call_sign(call_sign)
        record = EntityCallSign(
            call_sign=normalized, primary_call_sign=primary.call_sign, is_primary=False
        )
        self.call_signs.append(record)
        return record

    def promote_call_sign(self, call_sign, session):
        target = next(
            (item for item in self.call_signs if item.call_sign == normalize_call_sign(call_sign)),
            None,
        )
        primary = next((item for item in self.call_signs if item.is_primary), None)
        if target is None or target.is_primary or primary is None:
            raise ValueError("only an AKA call sign can be promoted")
        primary.is_primary = False
        primary.primary_call_sign = target.call_sign
        for item in self.call_signs:
            if item is not primary and item is not target:
                item.primary_call_sign = target.call_sign
        session.flush()
        target.is_primary = True
        target.primary_call_sign = target.call_sign

    def remove_aka_call_sign(self, call_sign):
        target = next(
            (item for item in self.call_signs if item.call_sign == normalize_call_sign(call_sign)),
            None,
        )
        if target is None or target.is_primary:
            raise ValueError("only an AKA call sign can be removed")
        self.call_signs.remove(target)


class EntityCallSign(Base):
    """A globally unique primary or AKA call sign belonging to an entity."""

    __tablename__ = "entity_call_signs"
    __table_args__ = (
        UniqueConstraint(
            "entity_id", "call_sign", "is_primary", name="uq_entity_call_sign_primary_role"
        ),
        ForeignKeyConstraint(
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
        CheckConstraint(
            "(is_primary = true AND call_sign = primary_call_sign) OR "
            "(is_primary = false AND call_sign <> primary_call_sign)",
            name="call_sign_requires_primary",
        ),
        CheckConstraint("primary_is_primary = true", name="call_sign_points_to_primary"),
        CheckConstraint("length(call_sign) BETWEEN 1 AND 32", name="valid_call_sign_length"),
        CheckConstraint("call_sign = upper(call_sign)", name="normalized_call_sign"),
        Index(
            "uq_entity_one_primary_call_sign",
            "entity_id",
            unique=True,
            sqlite_where=text("is_primary = 1"),
            postgresql_where=text("is_primary"),
        ),
    )

    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    call_sign: Mapped[str] = mapped_column(String(32), primary_key=True, unique=True)
    primary_call_sign: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    entity: Mapped[Entity] = relationship(back_populates="call_signs")

    @validates("call_sign")
    def normalize_call_sign(self, key, value):
        return normalize_call_sign(value)


class EntitySuperAdmin(Base):
    """An entity-level admin assignment to an external Keycloak user ID."""

    __tablename__ = "entity_super_admins"
    __table_args__ = (
        CheckConstraint("length(user_id) BETWEEN 1 AND 255", name="valid_admin_user_id"),
    )

    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    @validates("user_id")
    def validate_user_id(self, key, value):
        if not valid_user_id(value):
            raise ValueError("invalid admin user ID")
        return value
