"""Rotate PawReach staging seed credentials safely.

This operator-only script is intentionally database-direct. It does not expose a
runtime HTTP endpoint and refuses to run unless the caller explicitly targets
the staging environment and supplies the required confirmation phrase.

Expected environment variables:
- STAGING_DATABASE_URL: PostgreSQL connection URL for the hosted staging DB.
- STAGING_SEED_PASSWORD: new shared password for designated staging seed users.
- TARGET_ENVIRONMENT: must be exactly "staging".
- ROTATION_CONFIRMATION: must match CONFIRMATION_PHRASE exactly.

The script updates only the hard-coded seed-account allowlist in one transaction
and revokes all active refresh sessions for those users. Existing short-lived
access JWTs are not centrally revocable and will expire normally.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

import psycopg2
from argon2 import PasswordHasher


CONFIRMATION_PHRASE = "ROTATE_PAWREACH_STAGING_CREDENTIALS"

INSECURE_PATTERNS = (
    "stagingpass",
    "password",
    "admin123",
    "changeme",
    "pawsos",
    "pawreach",
    "12345678",
)

# Keep this list aligned with backend/scripts/seed_staging.py. These are
# synthetic staging-only accounts, never production identities.
STAGING_SEED_EMAILS = (
    "citizen@staging.pawsos.org",
    "superadmin@staging.pawsos.org",
    "admin@staging.pawsos.org",
    "admin.a@staging.pawsos.org",
    "rescuer.a@staging.pawsos.org",
    "rescuer.b@staging.pawsos.org",
    "vet@staging.pawsos.org",
    "admin.b@staging.pawsos.org",
    "rescuer.b1@staging.pawsos.org",
    "rescuer.b2@staging.pawsos.org",
    "vet.b@staging.pawsos.org",
)


@dataclass(frozen=True)
class RotationResult:
    users_rotated: int
    refresh_sessions_revoked: int


def validate_rotation_request(
    *,
    target_environment: str | None,
    confirmation: str | None,
    database_url: str | None,
    password: str | None,
) -> tuple[str, str]:
    """Validate operator intent and secrets before any database connection."""
    if (target_environment or "").strip().lower() != "staging":
        raise RuntimeError(
            "Credential rotation is staging-only. TARGET_ENVIRONMENT must be exactly 'staging'."
        )

    if confirmation != CONFIRMATION_PHRASE:
        raise RuntimeError(
            f"Rotation confirmation missing or invalid. Enter exactly: {CONFIRMATION_PHRASE}"
        )

    db_url = (database_url or "").strip()
    if not db_url:
        raise RuntimeError("STAGING_DATABASE_URL is required.")

    if db_url.startswith("postgresql+psycopg2://"):
        db_url = "postgresql://" + db_url.removeprefix("postgresql+psycopg2://")
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        raise ValueError("STAGING_DATABASE_URL must be a PostgreSQL connection URL.")

    new_password = (password or "").strip()
    if not new_password:
        raise RuntimeError("STAGING_SEED_PASSWORD is required.")
    if len(new_password) < 14:
        raise ValueError("STAGING_SEED_PASSWORD must be at least 14 characters long.")

    lowered = new_password.lower()
    for pattern in INSECURE_PATTERNS:
        if pattern in lowered:
            raise ValueError(
                f"STAGING_SEED_PASSWORD contains insecure or common pattern '{pattern}'."
            )

    return db_url, new_password


def rotate_credentials(
    *,
    database_url: str,
    new_password: str,
    dry_run: bool = False,
) -> RotationResult:
    """Rotate the staging seed allowlist atomically and revoke refresh sessions."""
    password_hasher = PasswordHasher()
    expected_emails = set(STAGING_SEED_EMAILS)

    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, email
                FROM users
                WHERE email = ANY(%s)
                ORDER BY email
                FOR UPDATE
                """,
                (list(STAGING_SEED_EMAILS),),
            )
            rows = cursor.fetchall()

            found_emails = {email for _, email in rows}
            missing = sorted(expected_emails - found_emails)
            unexpected = sorted(found_emails - expected_emails)
            if missing or unexpected or len(rows) != len(STAGING_SEED_EMAILS):
                details = []
                if missing:
                    details.append("missing=" + ",".join(missing))
                if unexpected:
                    details.append("unexpected=" + ",".join(unexpected))
                details.append(
                    f"expected_count={len(STAGING_SEED_EMAILS)}, found_count={len(rows)}"
                )
                raise RuntimeError(
                    "Staging seed-account allowlist mismatch; refusing partial rotation ("
                    + "; ".join(details)
                    + ")."
                )

            if dry_run:
                connection.rollback()
                return RotationResult(
                    users_rotated=0,
                    refresh_sessions_revoked=0,
                )

            # Generate a distinct Argon2 hash per account even though the staging
            # pilot intentionally shares one operator-managed password.
            for user_id, _email in rows:
                new_hash = password_hasher.hash(new_password)
                if not password_hasher.verify(new_hash, new_password):
                    raise RuntimeError("Argon2 self-verification failed; aborting rotation.")
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (new_hash, user_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Credential update affected an unexpected number of users; aborting."
                    )

            cursor.execute(
                """
                UPDATE refresh_sessions AS rs
                SET revoked_at = NOW()
                FROM users AS u
                WHERE rs.user_id = u.id
                  AND u.email = ANY(%s)
                  AND rs.revoked_at IS NULL
                """,
                (list(STAGING_SEED_EMAILS),),
            )
            revoked = cursor.rowcount

        connection.commit()
        return RotationResult(
            users_rotated=len(rows),
            refresh_sessions_revoked=revoked,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotate designated PawReach staging seed credentials."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify environment and exact seed-account allowlist without modifying data.",
    )
    args = parser.parse_args()

    database_url, password = validate_rotation_request(
        target_environment=os.getenv("TARGET_ENVIRONMENT"),
        confirmation=os.getenv("ROTATION_CONFIRMATION"),
        database_url=os.getenv("STAGING_DATABASE_URL"),
        password=os.getenv("STAGING_SEED_PASSWORD"),
    )

    result = rotate_credentials(
        database_url=database_url,
        new_password=password,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(
            f"Dry-run successful: exact staging seed allowlist contains "
            f"{len(STAGING_SEED_EMAILS)} users. No credentials were changed."
        )
    else:
        print(
            "Staging credential rotation successful: "
            f"users_rotated={result.users_rotated}, "
            f"refresh_sessions_revoked={result.refresh_sessions_revoked}."
        )
        print(
            "Short-lived access JWTs issued before rotation are not stored server-side "
            "and will expire according to the normal access-token TTL."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
