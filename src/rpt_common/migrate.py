"""Explicit schema administration, using separate writable credentials."""

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine


def upgrade(url, revision="head"):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    # Do not interpolate credentials into Alembic's ConfigParser or log them.
    engine = create_engine(url, hide_parameters=True)
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
