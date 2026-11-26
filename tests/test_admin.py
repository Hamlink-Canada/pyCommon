import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rpt_common.admin import (
    EntityNotFoundError,
    main,
    reset_entity_to_system_maintained,
    transfer_entity_owner,
)
from rpt_common.migrate import upgrade
from rpt_common.models import Entity, EntitySuperAdmin


def _database(tmp_path):
    url = f"sqlite:///{tmp_path / 'admin.db'}"
    upgrade(url)
    return url


def test_reset_entity_removes_shared_admins_and_preserves_entity(tmp_path):
    url = _database(tmp_path)
    engine = create_engine(url)
    entity = Entity(
        name="Maintained Entity",
        description="Keep this description",
        entity_type="club",
    )
    entity.assign_owner("old-owner")
    entity.add_primary_call_sign("VE3ABC")
    entity.add_aka_call_sign("VE3XYZ")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id
        session.add_all(
            [
                EntitySuperAdmin(entity_id=entity_id, user_id="admin-a"),
                EntitySuperAdmin(entity_id=entity_id, user_id="admin-b"),
            ]
        )

    assert reset_entity_to_system_maintained(url, entity_id) == 2
    with Session(engine) as session:
        reset = session.get(Entity, entity_id)
        assert reset.owner_user_id is None
        assert reset.is_system_maintained is True
        assert reset.name == "Maintained Entity"
        assert reset.description == "Keep this description"
        assert {sign.call_sign for sign in reset.call_signs} == {"VE3ABC", "VE3XYZ"}
        assert session.scalars(select(EntitySuperAdmin)).all() == []
    engine.dispose()


def test_reset_entity_rejects_missing_entity(tmp_path):
    url = _database(tmp_path)
    with pytest.raises(EntityNotFoundError):
        reset_entity_to_system_maintained(url, 42)


def test_transfer_entity_owner_updates_existing_entity(tmp_path):
    url = _database(tmp_path)
    engine = create_engine(url)
    entity = Entity(name="Transferable Entity", entity_type="club")
    entity.assign_owner("old-owner")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id

    transfer_entity_owner(url, entity_id, "new-owner")
    with Session(engine) as session:
        transferred = session.scalar(select(Entity).where(Entity.id == entity_id))
        assert transferred.owner_user_id == "new-owner"
        assert transferred.is_system_maintained is False
    engine.dispose()


def test_transfer_entity_owner_rejects_missing_entity_and_invalid_subject(tmp_path):
    url = _database(tmp_path)
    engine = create_engine(url)
    entity = Entity(name="Transfer Rollback Entity", entity_type="club")
    entity.assign_owner("original-owner")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id

    with pytest.raises(EntityNotFoundError):
        transfer_entity_owner(url, entity_id + 100, "new-owner")
    with pytest.raises(ValueError, match="invalid owner"):
        transfer_entity_owner(url, entity_id, " invalid ")
    with Session(engine) as session:
        persisted = session.get(Entity, entity_id)
        assert persisted.owner_user_id == "original-owner"
        assert persisted.is_system_maintained is False
    engine.dispose()


def test_transfer_entity_owner_cli_uses_configured_database(tmp_path, monkeypatch, capsys):
    url = _database(tmp_path)
    engine = create_engine(url)
    entity = Entity(name="CLI Transfer Entity", entity_type="club")
    entity.assign_owner("original-owner")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id
    engine.dispose()

    monkeypatch.setenv("RPT_MIGRATION_DATABASE_URL", url)
    main(["transfer-entity-owner", str(entity_id), "replacement-owner"])
    assert (
        f"Entity {entity_id} ownership transferred to replacement-owner" in capsys.readouterr().out
    )


def test_reset_entity_cli_uses_configured_database(tmp_path, monkeypatch, capsys):
    url = _database(tmp_path)
    engine = create_engine(url)
    entity = Entity(name="CLI Reset Entity", entity_type="club")
    entity.assign_owner("original-owner")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id
        session.add(EntitySuperAdmin(entity_id=entity_id, user_id="old-admin"))
    engine.dispose()

    monkeypatch.setenv("RPT_MIGRATION_DATABASE_URL", url)
    main(["reset-entity", str(entity_id)])
    assert "removed 1 Entity Super Admin assignment" in capsys.readouterr().out

    engine = create_engine(url)
    with Session(engine) as session:
        reset = session.get(Entity, entity_id)
        assert reset.owner_user_id is None
        assert reset.is_system_maintained is True
        assert session.scalars(select(EntitySuperAdmin)).all() == []
    engine.dispose()


def test_admin_cli_reports_uncertain_outcome_on_database_error(monkeypatch, capsys):
    monkeypatch.setenv("RPT_MIGRATION_DATABASE_URL", "sqlite:///unused.db")
    monkeypatch.setattr(
        "rpt_common.admin.transfer_entity_owner",
        lambda *args: (_ for _ in ()).throw(RuntimeError("connection lost")),
    )
    with pytest.raises(SystemExit) as error:
        main(["transfer-entity-owner", "7", "owner"])
    assert error.value.code == 1
    stderr = capsys.readouterr().err
    assert "outcome may be unknown" in stderr
    assert "connection lost" not in stderr
