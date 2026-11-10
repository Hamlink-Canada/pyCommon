"""Shared node credentials. Passwords must never appear in object representations."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, String, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates

SCHEMA_REVISION = "0001_node_credentials"
SUPPORTED_REVISIONS = frozenset({SCHEMA_REVISION})


def valid_node_id(value):
    return type(value) is int and 0 < value <= 2**63 - 1


def valid_password(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 79
        and all(33 <= ord(character) <= 126 for character in value)
    )


class Base(DeclarativeBase):
    pass


class NodeCredential(Base):
    __tablename__ = "node_credentials"
    __table_args__ = (
        CheckConstraint("node_id > 0 AND node_id <= 9223372036854775807", name="positive_node_id"),
        CheckConstraint("length(password) BETWEEN 1 AND 79", name="password_length"),
    )

    node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    password: Mapped[str] = mapped_column(String(79), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    @validates("node_id")
    def validate_node(self, key, value):
        if not valid_node_id(value):
            raise ValueError("invalid node ID")
        return value

    @validates("password")
    def validate_password(self, key, value):
        if not valid_password(value):
            raise ValueError("invalid registration password")
        return value
