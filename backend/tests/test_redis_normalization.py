import logging
import pytest
from app.tasks.celery_app import normalize_celery_redis_url


def test_normalize_redis_url_plain_redis_unchanged():
    """Verify standard non-TLS redis:// URLs remain completely unchanged."""
    url = "redis://localhost:6379/0"
    assert normalize_celery_redis_url(url) == url

    url_with_auth = "redis://:localpass@127.0.0.1:6379/1?health_check_interval=30"
    assert normalize_celery_redis_url(url_with_auth) == url_with_auth


def test_normalize_redis_url_rediss_missing_ssl_cert_reqs():
    """Verify rediss:// URLs automatically append ssl_cert_reqs=required for secure TLS verification."""
    url = "rediss://default:supersecret123@global-example.upstash.io:6379"
    normalized = normalize_celery_redis_url(url)
    assert "ssl_cert_reqs=required" in normalized
    assert normalized == "rediss://default:supersecret123@global-example.upstash.io:6379?ssl_cert_reqs=required"


def test_normalize_redis_url_rediss_with_existing_query_appends_safely():
    """Verify rediss:// URLs with existing parameters append ssl_cert_reqs safely with '&', not '?'."""
    url = "rediss://default:supersecret123@global-example.upstash.io:6379/0?db=0&timeout=5"
    normalized = normalize_celery_redis_url(url)
    assert normalized.count("?") == 1
    assert "db=0" in normalized
    assert "timeout=5" in normalized
    assert "ssl_cert_reqs=required" in normalized
    assert normalized == "rediss://default:supersecret123@global-example.upstash.io:6379/0?db=0&timeout=5&ssl_cert_reqs=required"


def test_normalize_redis_url_rediss_already_configured_not_duplicated():
    """Verify rediss:// URLs that already have ssl_cert_reqs=required are not duplicated."""
    url = "rediss://default:supersecret123@global-example.upstash.io:6379?ssl_cert_reqs=required"
    normalized = normalize_celery_redis_url(url)
    assert normalized.count("ssl_cert_reqs") == 1
    assert normalized == url


def test_normalize_redis_url_credentials_not_logged(caplog):
    """Verify that credentials / passwords in REDIS_URL are never leaked into logs during normalization."""
    secret_pass = "extremely_sensitive_upstash_secret_98765"
    url = f"rediss://default:{secret_pass}@example.upstash.io:6379"
    with caplog.at_level(logging.DEBUG):
        normalized = normalize_celery_redis_url(url)
        assert secret_pass in normalized  # function returns valid connection URL
        for record in caplog.records:
            assert secret_pass not in record.message  # credentials never emitted to logs


def test_normalize_redis_url_handles_empty_and_none():
    """Verify empty or None values return cleanly without exception."""
    assert normalize_celery_redis_url("") == ""
    assert normalize_celery_redis_url(None) is None


def test_redis_py_readiness_compatibility_with_normalized_url():
    """Verify redis-py parses the normalized rediss:// connection URL properly into SSL connection kwargs."""
    import redis
    url = "rediss://default:secret123@example.upstash.io:6379"
    normalized = normalize_celery_redis_url(url)
    client = redis.from_url(normalized)
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("ssl_cert_reqs") == "required"
    assert conn_kwargs.get("host") == "example.upstash.io"
    assert conn_kwargs.get("port") == 6379
