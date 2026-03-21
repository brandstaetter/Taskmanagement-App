import hashlib

from taskmanagement_app.utils.gravatar import gravatar_url


def test_gravatar_url_basic() -> None:
    url = gravatar_url("user@example.com")
    expected_hash = hashlib.sha256(b"user@example.com").hexdigest()
    assert f"https://www.gravatar.com/avatar/{expected_hash}" in url


def test_gravatar_url_normalizes_email_case() -> None:
    url_lower = gravatar_url("user@example.com")
    url_upper = gravatar_url("USER@EXAMPLE.COM")
    assert url_lower == url_upper


def test_gravatar_url_strips_whitespace() -> None:
    url_clean = gravatar_url("user@example.com")
    url_padded = gravatar_url("  user@example.com  ")
    assert url_clean == url_padded


def test_gravatar_url_default_size() -> None:
    url = gravatar_url("user@example.com")
    assert "s=80" in url


def test_gravatar_url_custom_size() -> None:
    url = gravatar_url("user@example.com", size=200)
    assert "s=200" in url


def test_gravatar_url_default_fallback() -> None:
    url = gravatar_url("user@example.com")
    assert "d=identicon" in url


def test_gravatar_url_custom_fallback() -> None:
    url = gravatar_url("user@example.com", default="robohash")
    assert "d=robohash" in url


def test_gravatar_url_uses_sha256() -> None:
    email = "test@example.com"
    expected_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    url = gravatar_url(email)
    assert expected_hash in url


def test_gravatar_url_different_emails_produce_different_urls() -> None:
    url1 = gravatar_url("alice@example.com")
    url2 = gravatar_url("bob@example.com")
    assert url1 != url2
