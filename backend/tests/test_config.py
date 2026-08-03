import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def clear_product_environment(monkeypatch):
    monkeypatch.delenv("HETREN_ENV", raising=False)
    monkeypatch.delenv("OVRIN_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")


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
