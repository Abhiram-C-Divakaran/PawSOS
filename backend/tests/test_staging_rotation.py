"""Security tests for operator-only staging credential rotation."""

import pytest

from scripts.rotate_staging_credentials import (
    CONFIRMATION_PHRASE,
    STAGING_SEED_EMAILS,
    validate_rotation_request,
)


VALID_PASSWORD = "Kx9#mQ2$vL8!zT5_secure"
VALID_DATABASE_URL = "postgresql://example.invalid/pawreach_staging"


def valid_request(**overrides):
    values = {
        "target_environment": "staging",
        "confirmation": CONFIRMATION_PHRASE,
        "database_url": VALID_DATABASE_URL,
        "password": VALID_PASSWORD,
    }
    values.update(overrides)
    return validate_rotation_request(**values)


def test_rotation_allowlist_is_exact_and_unique():
    assert len(STAGING_SEED_EMAILS) == 11
    assert len(set(STAGING_SEED_EMAILS)) == len(STAGING_SEED_EMAILS)
    assert all(email.endswith("@staging.pawsos.org") for email in STAGING_SEED_EMAILS)


@pytest.mark.parametrize("target", [None, "", "development", "production", "prod"])
def test_rotation_refuses_non_staging_environment(target):
    with pytest.raises(RuntimeError, match="staging-only"):
        valid_request(target_environment=target)


def test_rotation_requires_exact_confirmation_phrase():
    with pytest.raises(RuntimeError, match="confirmation"):
        valid_request(confirmation="yes")


def test_rotation_requires_database_url():
    with pytest.raises(RuntimeError, match="STAGING_DATABASE_URL"):
        valid_request(database_url="")


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///pawsos.db",
        "mysql://user:pass@example.invalid/db",
        "https://example.invalid/db",
    ],
)
def test_rotation_rejects_non_postgresql_urls(database_url):
    with pytest.raises(ValueError, match="PostgreSQL"):
        valid_request(database_url=database_url)


def test_rotation_normalizes_sqlalchemy_psycopg2_url():
    database_url, password = valid_request(
        database_url="postgresql+psycopg2://example.invalid/pawreach_staging"
    )
    assert database_url == "postgresql://example.invalid/pawreach_staging"
    assert password == VALID_PASSWORD


def test_rotation_rejects_missing_password():
    with pytest.raises(RuntimeError, match="STAGING_SEED_PASSWORD"):
        valid_request(password="")


def test_rotation_rejects_short_password():
    with pytest.raises(ValueError, match="at least 14"):
        valid_request(password="TooShort9!")


@pytest.mark.parametrize(
    "password",
    [
        "stagingpass_xY9!secure",
        "my_password_is_long_enough",
        "admin123_xY9!secure_long",
        "changeme_xY9!secure_long",
        "pawsos_xY9!secure_long",
        "pawreach_xY9!secure_long",
        "secret_12345678_xY9!",
    ],
)
def test_rotation_rejects_insecure_password_patterns(password):
    with pytest.raises(ValueError, match="insecure or common pattern"):
        valid_request(password=password)


def test_rotation_accepts_strong_password_and_staging_request():
    database_url, password = valid_request()
    assert database_url == VALID_DATABASE_URL
    assert password == VALID_PASSWORD
