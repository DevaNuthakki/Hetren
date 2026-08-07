import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def clear_product_environment(monkeypatch):
    monkeypatch.delenv("HETREN_ENV", raising=False)
    monkeypatch.delenv("OVRIN_ENV", raising=False)
    monkeypatch.delenv("HETREN_AUTH_SECRET_KEY", raising=False)
    monkeypatch.delenv(
        "HETREN_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
        raising=False,
    )
    monkeypatch.delenv(
        "HETREN_AUTH_REFRESH_TOKEN_EXPIRE_DAYS",
        raising=False,
    )
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv(
        "HETREN_AUTH_SECRET_KEY",
        "test-auth-secret-key-with-at-least-32-characters",
    )


def test_settings_load_hetren_environment(monkeypatch):
    monkeypatch.setenv("HETREN_ENV", "staging")

    settings = Settings(_env_file=None)

    assert settings.app_env == "staging"


def test_settings_accept_legacy_ovrin_environment(monkeypatch):
    monkeypatch.setenv("OVRIN_ENV", "test")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"


def test_hetren_environment_takes_precedence(monkeypatch):
    monkeypatch.setenv("HETREN_ENV", "production")
    monkeypatch.setenv("OVRIN_ENV", "development")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"


def test_auth_settings_use_secure_defaults():
    settings = Settings(_env_file=None)

    assert (
        settings.auth_secret_key.get_secret_value()
        == "test-auth-secret-key-with-at-least-32-characters"
    )
    assert settings.auth_access_token_expire_minutes == 15
    assert settings.auth_refresh_token_expire_days == 30


def test_auth_settings_load_environment_overrides(monkeypatch):
    monkeypatch.setenv(
        "HETREN_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
        "20",
    )
    monkeypatch.setenv(
        "HETREN_AUTH_REFRESH_TOKEN_EXPIRE_DAYS",
        "45",
    )

    settings = Settings(_env_file=None)

    assert settings.auth_access_token_expire_minutes == 20
    assert settings.auth_refresh_token_expire_days == 45


def test_auth_settings_require_secret(monkeypatch):
    monkeypatch.delenv("HETREN_AUTH_SECRET_KEY")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_auth_settings_reject_short_secret(monkeypatch):
    monkeypatch.setenv("HETREN_AUTH_SECRET_KEY", "too-short")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    [
        ("HETREN_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "0"),
        ("HETREN_AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "0"),
    ],
)
def test_auth_settings_reject_non_positive_expiration(
    monkeypatch,
    environment_name,
    invalid_value,
):
    monkeypatch.setenv(environment_name, invalid_value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
