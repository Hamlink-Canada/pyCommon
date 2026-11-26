"""Explicit schema administration, using separate writable credentials."""

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def upgrade(url, revision="head"):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    # Do not interpolate credentials into Alembic's ConfigParser or log them.
    database_url = make_url(url)
    engine_options = {"hide_parameters": True}
    # sqlite3's legacy transaction mode leaves DDL outside the transaction,
    # so a failed multi-step upgrade can leave a partial schema behind.
    if database_url.get_backend_name() == "sqlite":
        engine_options["connect_args"] = {"autocommit": False}
    engine = create_engine(database_url, **engine_options)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Apply shared schema migrations explicitly")
    parser.add_argument("action", choices=["upgrade"])
    parser.add_argument("revision", nargs="?", default="head")
    parser.add_argument("--url-file", help="Read the writable database URL from a mounted secret")
    args = parser.parse_args()
    try:
        url = (
            Path(args.url_file).read_text().strip()
            if args.url_file
            else os.environ["RPT_MIGRATION_DATABASE_URL"]
        )
        upgrade(url, args.revision)
    except Exception:
        parser.exit(1, "Migration failed; check the writable connection and schema revision.\n")
