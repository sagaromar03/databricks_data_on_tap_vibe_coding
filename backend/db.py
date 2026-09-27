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


def _connect_via_env():
    """Databricks App path: PG* connection details are injected as env vars."""
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", DATABASE_NAME),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        sslmode=os.environ.get("PGSSLMODE", "require"),
    )


def _connect_via_sdk():
    """Local / notebook path: mint a short-lived OAuth token via the SDK."""
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    instance = w.database.get_database_instance(name=INSTANCE_NAME)
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[INSTANCE_NAME],
    )
    return psycopg2.connect(
        host=instance.read_write_dns,
        dbname=DATABASE_NAME,
        user=w.current_user.me().user_name,
        password=cred.token,
        sslmode="require",
    )


def get_connection():
    """Return a live psycopg2 connection, detecting the runtime environment."""
    if os.environ.get("PGHOST") and os.environ.get("PGPASSWORD"):
        return _connect_via_env()
    return _connect_via_sdk()


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
