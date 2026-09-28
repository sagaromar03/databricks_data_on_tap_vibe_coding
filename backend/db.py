"""All database connection logic for Data on Tap.

Nothing else in the codebase calls psycopg2.connect(). get_connection() detects
its environment and returns a live connection either way:

  - Databricks App: connection details injected as standard PG* env vars.
  - Local / notebook: an OAuth token generated in code via the Databricks SDK
    (never a static password); the host also comes from the SDK.

This single point of isolation is what makes the app interchangeable between a
deployed Databricks App and a local `streamlit run`.
"""

import os
import uuid
import contextlib

import psycopg2

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "data-on-tap")
DATABASE_NAME = os.environ.get("PGDATABASE", "databricks_postgres")


def _generate_token(instance_names):
    """Mint a short-lived OAuth token via the SDK; the token is the PG password."""
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=list(instance_names),
    )
    return w, cred.token


def _connect_app():
    """Databricks App path: PG* connection details are injected as env vars.

    The app runs as a service principal; PGUSER is the SP's client id (its
    Postgres role). PGPASSWORD is NOT injected — we mint an OAuth token via the
    SDK and use it as the password. That role must be GRANTed table privileges.
    """
    _, token = _generate_token([INSTANCE_NAME])
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", DATABASE_NAME),
        user=os.environ["PGUSER"],
        password=token,
        sslmode=os.environ.get("PGSSLMODE", "require"),
    )


def _connect_local():
    """Local / notebook path: host from the SDK, connect as the current user."""
    w, token = _generate_token([INSTANCE_NAME])
    instance = w.database.get_database_instance(name=INSTANCE_NAME)
    return psycopg2.connect(
        host=instance.read_write_dns,
        dbname=DATABASE_NAME,
        user=w.current_user.me().user_name,
        password=token,
        sslmode="require",
    )


def get_connection():
    """Return a live psycopg2 connection, detecting the runtime environment."""
    if os.environ.get("PGHOST"):
        return _connect_app()
    return _connect_local()


@contextlib.contextmanager
def connection():
    """Context manager that yields a connection and always closes it.

    Transaction control (commit / rollback) is left to the caller via
    `with conn:` so a failed order rolls back cleanly.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
