"""Customer authentication for Data on Tap.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only, no extra dependency)
and never stored or logged in plaintext. Stored format:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

sign_up / log_in return a small customer dict ({customer_id, name, email}) that
the UI keeps in session; the password hash never leaves this module.
"""

import hashlib
import hmac
import secrets

from .db import connection

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


class AuthError(Exception):
    """Raised for any signup/login failure shown to the user."""


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def sign_up(name, email, password):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or not email or not password:
        raise AuthError("Name, email, and password are all required.")
    if "@" not in email:
        raise AuthError("Enter a valid email address.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")

    with connection() as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM customers WHERE lower(email) = %s", (email,))
                if cur.fetchone():
                    raise AuthError("An account with that email already exists.")
                cur.execute(
                    """
                    INSERT INTO customers (name, email, phone, password_hash)
                    VALUES (%s, %s, %s, %s)
                    RETURNING customer_id, name, email
                    """,
                    (name, email, None, hash_password(password)),
                )
                customer_id, cname, cemail = cur.fetchone()
    return {"customer_id": customer_id, "name": cname, "email": cemail}


def log_in(email, password):
    email = (email or "").strip().lower()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, name, email, password_hash FROM customers WHERE lower(email) = %s",
            (email,),
        )
        row = cur.fetchone()
    # Uniform error — never reveal whether the email exists.
    if row is None or row[3] is None or not verify_password(password, row[3]):
        raise AuthError("Invalid email or password.")
    return {"customer_id": row[0], "name": row[1], "email": row[2]}
