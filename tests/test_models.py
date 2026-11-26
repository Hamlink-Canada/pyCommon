import pytest
from sqlalchemy import create_engine, event, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rpt_common.migrate import upgrade
from rpt_common.models.credentials import SCHEMA_REVISION, NodeCredential
from rpt_common.models.entities import Entity, EntityCallSign, EntitySuperAdmin


def test_migration_defaults_constraints_and_repeat(tmp_path):
    url = f"sqlite:///{tmp_path / 'credentials.db'}"
    upgrade(url)
    upgrade(url)
    engine = create_engine(url)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
        connection.execute(insert(NodeCredential).values(node_id=1234, password="generated-secret"))
    with Session(engine) as session:
        node = session.scalar(select(NodeCredential))
        assert node.node_id == 1234 and node.enabled is False
        assert "generated-secret" not in repr(node)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO node_credentials(password) VALUES ('password')"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(NodeCredential).values(node_id=0, password="password"))
    engine.dispose()


@pytest.mark.parametrize("node", [True, 0, -1, 2**63, "1234"])
def test_model_validates_node(node):
    with pytest.raises(ValueError):
        NodeCredential(node_id=node, password="generated-secret")


@pytest.mark.parametrize("password", ["", "a b", "x" * 80, "café", "hidden\n"])
def test_model_validates_password(password):
    with pytest.raises(ValueError):
        NodeCredential(node_id=1234, password=password)


def test_entity_ownership_and_admin_assignments(tmp_path):
    url = f"sqlite:///{tmp_path / 'entities.db'}"
    upgrade(url)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    entity = Entity(name="Example Radio Club", entity_type="club")
    entity.assign_owner("keycloak-subject-1")
    assert entity.owner_user_id == "keycloak-subject-1"
    assert entity.is_system_maintained is False
    entity.return_to_system_maintained()
    assert entity.owner_user_id is None
    assert entity.is_system_maintained is True

    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id
        session.add_all(
            [
                EntitySuperAdmin(entity_id=entity.id, user_id="subject-a"),
                EntitySuperAdmin(entity_id=entity.id, user_id="subject-b"),
            ]
        )
    with Session(engine) as session:
        admins = session.scalars(select(EntitySuperAdmin)).all()
        assert {admin.user_id for admin in admins} == {"subject-a", "subject-b"}
        assert session.scalar(select(Entity).where(Entity.id == entity_id)).call_signs == []
    engine.dispose()


def test_entity_call_sign_rules_and_promotion(tmp_path):
    url = f"sqlite:///{tmp_path / 'call-signs.db'}"
    upgrade(url)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    entity = Entity(name="Example Radio Club", entity_type="club")
    with pytest.raises(ValueError, match="requires a primary"):
        entity.add_aka_call_sign("VE3XYZ")
    entity.add_primary_call_sign(" ve3abc ")
    entity.add_aka_call_sign("VE3XYZ")
    entity.add_aka_call_sign("VE3AAA")

    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                insert(EntityCallSign).values(
                    entity_id=entity_id,
                    call_sign="VE3BAD",
                    primary_call_sign="VE3AAA",
                    primary_is_primary=True,
                    is_primary=False,
                )
            )

    with Session(engine) as session, session.begin():
        loaded = session.get(Entity, entity_id)
        loaded.promote_call_sign("ve3xyz", session)
    with Session(engine) as session:
        signs = session.scalars(select(EntityCallSign).order_by(EntityCallSign.call_sign)).all()
        assert [(sign.call_sign, sign.is_primary) for sign in signs] == [
            ("VE3AAA", False),
            ("VE3ABC", False),
            ("VE3XYZ", True),
        ]
        loaded = session.get(Entity, entity_id)
        loaded.remove_aka_call_sign("ve3abc")
        loaded.remove_aka_call_sign("ve3aaa")
        session.commit()
    with Session(engine) as session:
        signs = session.scalars(select(EntityCallSign.call_sign)).all()
        assert signs == ["VE3XYZ"]
    engine.dispose()


def test_entity_delete_cascades_primary_and_aka_signs(tmp_path):
    url = f"sqlite:///{tmp_path / 'delete-entity.db'}"
    upgrade(url)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    entity = Entity(name="Delete Me", entity_type="club")
    entity.add_primary_call_sign("VE3ABC")
    entity.add_aka_call_sign("VE3XYZ")
    with Session(engine) as session, session.begin():
        session.add(entity)
        session.flush()
        entity_id = entity.id
    with Session(engine) as session, session.begin():
        session.delete(session.get(Entity, entity_id))
    with Session(engine) as session:
        assert session.scalars(select(EntityCallSign)).all() == []
    engine.dispose()


def test_entity_type_and_call_sign_normalization():
    with pytest.raises(ValueError, match="invalid entity type"):
        Entity(name="Test", entity_type="repeater")
    entity = Entity(name="Test", entity_type="organization")
    with pytest.raises(ValueError, match="invalid call sign"):
        entity.add_primary_call_sign("NOT A CALL")
    with pytest.raises(ValueError, match="invalid owner"):
        entity.assign_owner(" subject ")
