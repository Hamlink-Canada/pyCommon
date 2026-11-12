import sys

from rpt_common import migrate


def test_upgrade_disposes_engine_when_migration_fails(monkeypatch):
    disposed = []

    class Engine:
        def begin(self):
            raise AssertionError("the context manager should be mocked")

        def dispose(self):
            disposed.append(True)

    engine = Engine()
    monkeypatch.setattr(migrate, "create_engine", lambda url, **kwargs: engine)

    class ConnectionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    engine.begin = lambda: ConnectionContext()

    def fail(config, revision):
        assert config.attributes["connection"] is not None
        raise RuntimeError("migration failed")

    monkeypatch.setattr(migrate.command, "upgrade", fail)
    try:
        migrate.upgrade("sqlite:///unused.db")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the migration error to propagate")
    assert disposed == [True]


def test_migration_cli_reads_url_file_and_forwards_revision(monkeypatch, tmp_path):
    secret = tmp_path / "database-url"
    secret.write_text("sqlite:///example.db\n")
    calls = []
    monkeypatch.setattr(migrate, "upgrade", lambda url, revision: calls.append((url, revision)))
    monkeypatch.setattr(sys, "argv", ["rpt-migrate", "upgrade", "0001", "--url-file", str(secret)])

    migrate.main()
    assert calls == [("sqlite:///example.db", "0001")]


def test_migration_cli_hides_failure_details(monkeypatch, capsys):
    monkeypatch.setenv("RPT_MIGRATION_DATABASE_URL", "sqlite:///unused.db")
    monkeypatch.setattr(migrate, "upgrade", lambda *args: (_ for _ in ()).throw(RuntimeError("secret")))
    monkeypatch.setattr(sys, "argv", ["rpt-migrate", "upgrade"])

    try:
        migrate.main()
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError("expected parser exit")
    assert "secret" not in capsys.readouterr().err
