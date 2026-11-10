# Own the shared credential model and its migrations

The shared library owns the SQLAlchemy NodeCredential model and versioned migrations so Central Auth and the future provisioning project use one database definition. Central Auth only reads enabled credentials and validates schema compatibility; operators or deployment jobs apply migrations with separate writable credentials. This avoids schema changes during credential-service startup at the cost of coordinating model versions, migrations, and deployment order.
