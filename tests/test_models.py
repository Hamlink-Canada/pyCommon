import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rpt_common.migrate import upgrade
from rpt_common.models.credentials import SCHEMA_REVISION, NodeCredential


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
