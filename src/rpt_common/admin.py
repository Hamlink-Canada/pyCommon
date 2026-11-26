"""Local maintenance operations for shared cross-product records."""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker

from rpt_common.models import Entity, EntitySuperAdmin


class EntityNotFoundError(Exception):
    """Raised when an administrative operation targets a missing Entity."""


def reset_entity_to_system_maintained(database_url, entity_id):
    """Remove shared Entity admins and return the Entity to system ownership."""
    engine = create_engine(database_url, hide_parameters=True)
    session_factory = sessionmaker(engine)
    try:
        with session_factory.begin() as session:
            entity = session.scalar(select(Entity).where(Entity.id == entity_id).with_for_update())
            if entity is None:
                raise EntityNotFoundError(f"Entity {entity_id} does not exist")

            removed_count = session.scalar(
                select(func.count())
                .select_from(EntitySuperAdmin)
                .where(EntitySuperAdmin.entity_id == entity_id)
            )
            session.execute(delete(EntitySuperAdmin).where(EntitySuperAdmin.entity_id == entity_id))
            entity.return_to_system_maintained()
            session.flush()
        return removed_count or 0
    finally:
        engine.dispose()


def transfer_entity_owner(database_url, entity_id, owner_user_id):
    """Transfer a shared Entity to a specified user in one transaction."""
    engine = create_engine(database_url, hide_parameters=True)
    session_factory = sessionmaker(engine)
    try:
        with session_factory.begin() as session:
            entity = session.scalar(select(Entity).where(Entity.id == entity_id).with_for_update())
            if entity is None:
                raise EntityNotFoundError(f"Entity {entity_id} does not exist")
            entity.assign_owner(owner_user_id)
            session.flush()
    finally:
        engine.dispose()


def _positive_entity_id(value):
    try:
        entity_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Entity ID must be a positive integer") from error
    if entity_id <= 0:
        raise argparse.ArgumentTypeError("Entity ID must be a positive integer")
    return entity_id


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rpt-common-admin",
        description="Local maintenance operations for shared cross-product records",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    reset_parser = commands.add_parser(
        "reset-entity",
        help="remove shared Entity Super Admins and return an Entity to system-maintained status",
    )
    reset_parser.add_argument("entity_id", type=_positive_entity_id)
    reset_parser.add_argument(
        "--url-file", help="Read the writable database URL from a mounted secret"
    )
    transfer_parser = commands.add_parser(
        "transfer-entity-owner", help="transfer a shared Entity to a user subject"
    )
    transfer_parser.add_argument("entity_id", type=_positive_entity_id)
    transfer_parser.add_argument("owner_user_id", help="new owner's OIDC subject")
    transfer_parser.add_argument(
        "--url-file", help="Read the writable database URL from a mounted secret"
    )
    args = parser.parse_args(argv)

    try:
        database_url = (
            Path(args.url_file).read_text(encoding="utf-8").strip()
            if args.url_file
            else os.environ["RPT_MIGRATION_DATABASE_URL"]
        )
        if not database_url:
            raise ValueError("database URL is empty")
        if args.command == "reset-entity":
            removed_count = reset_entity_to_system_maintained(database_url, args.entity_id)
        else:
            transfer_entity_owner(database_url, args.entity_id, args.owner_user_id)
    except EntityNotFoundError as error:
        parser.exit(1, f"{error}; no changes were made.\n")
    except Exception:
        parser.exit(
            1,
            "Entity administration failed; the operation outcome may be unknown. "
            "Verify database state before retrying.\n",
        )

    if args.command == "reset-entity":
        assignment_label = "assignment" if removed_count == 1 else "assignments"
        print(
            f"Entity {args.entity_id} returned to system-maintained status; "
            f"removed {removed_count} Entity Super Admin {assignment_label}."
        )
    else:
        print(f"Entity {args.entity_id} ownership transferred to {args.owner_user_id}.")


if __name__ == "__main__":
    main()
