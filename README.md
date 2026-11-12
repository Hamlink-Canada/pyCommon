# Shared Python utilities

`pyCommon` holds Python code shared across projects, initially the SQLAlchemy
credential model and its versioned migrations. Database models live under
`rpt_common.models`; other shared modules can live alongside that package. Central Auth reads this model. Provisioning and credential lifecycle management are
outside this library. There is no running service,
container image, or PyPI publication for this library.

## Model and requirements

Python 3.13+ is required. The import namespace is `rpt_common` and the distribution
name is `rpt-common`. SQLAlchemy and Alembic are runtime dependencies; the `postgres`
extra installs Psycopg for PostgreSQL. SQLite is for development/testing. PostgreSQL
is the documented production engine.

`rpt_common.models.credentials.NodeCredential` maps to `node_credentials`:

| Column | Meaning |
| --- | --- |
| `node_id` | Explicit positive signed-64-bit primary key; never generated automatically |
| `password` | Required generated password, 1–79 printable ASCII characters without whitespace |
| `enabled` | Defaults to false; disabled credentials cannot be retrieved |

There is one current credential per node in one network's database. The model does
not contain service tokens, registrar identities, accounts, or registration history.
Python validation enforces the password format; consumers must also validate stored
results because external SQL can bypass Python validators. Never include model
passwords in logs, object dumps, or error payloads.

## Run migrations explicitly

Use a writable migration account, separate from Central Auth's read-only account.
Install the appropriate extra and supply a URL through a mounted file or
`RPT_MIGRATION_DATABASE_URL`. Prefer a file for production credentials:

```sh
rpt-common-migrate upgrade --url-file /run/secrets/migration-url
```

For a local SQLite database:

```sh
RPT_MIGRATION_DATABASE_URL=sqlite:////tmp/rpt-credentials.db rpt-common-migrate upgrade
```

`upgrade` defaults to `head` and can be repeated. This command is an explicit
administrative operation; Central Auth never runs it at startup. PostgreSQL URLs
should include `sslmode=verify-full` and the appropriate `sslrootcert` path. The
migration command passes the URL to SQLAlchemy without weakening its TLS options.
Do not pass credentials in command-line arguments or commit URL files.

After migration, grant the lookup account CONNECT, schema USAGE, and SELECT on
`node_credentials` and `alembic_version`; do not grant credential writes. Provisioning
and migration accounts have separate responsibilities. Central Auth validates a
known supported revision; migration compatibility must be tested before rollout.

The initial revision is `0001_node_credentials`. Schema definitions and migrations
must be reviewed together. Fresh-install and repeated-upgrade tests cover SQLite;
the Central Auth acceptance suite also exercises PostgreSQL and a SELECT-only role.

## Docker/Kubernetes migration job

The Central Auth image includes this library and `rpt-common-migrate`. Its README
contains a migration Job example that overrides the normal service command and
mounts separate writable credentials. Run that job deliberately before deploying a
service requiring the new schema; do not attach it as every Pod's startup action.

Detailed operation guidance is maintained in the
[shared-library documentation](https://hamlink-canada.github.io/apt-rpt-docs/projects/common/).

## Development

```sh
uv sync --locked --all-extras
make check test build
```

Bindings remain in `rpt_protobuf`; database models and migrations belong here.
Central Auth follows this repository's `main` branch, with an editable sibling
checkout during development. Its CI resolves both shared dependencies once per run.

The library has no application-level configuration loader or database connection
at import time. Migration resources are included in wheels and source distributions.
See [current decisions](docs/decisions.md) for model and migration ownership.

## License

[AGPL-3.0-or-later](LICENSE).
