import pytest
from pydantic import ValidationError

from app.runner_config import LocalRunnerSettings


RUNNER_ENVIRONMENT_KEYS = (
    "OVRIN_RUNNER_API_URL",
    "OVRIN_RUNNER_CREDENTIAL",
    "OVRIN_RUNNER_VERSION",
    "OVRIN_RUNNER_CAPABILITIES",
    "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS",
    "OVRIN_RUNNER_LEASE_SECONDS",
)


def clear_runner_environment(monkeypatch):
    for key in RUNNER_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_local_runner_settings_load_environment(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    monkeypatch.setenv(
        "OVRIN_RUNNER_API_URL",
        "https://ovrin.example.com/",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_VERSION",
        " 0.2.0 ",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CAPABILITIES",
        '[" ASR ", "cpu", "asr", "local"]',
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS",
        "45",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_SECONDS",
        "600",
    )

    settings = LocalRunnerSettings(_env_file=None)

    assert settings.api_base_url == (
        "https://ovrin.example.com"
    )
    assert (
        settings.credential.get_secret_value()
        == "ovrin_runner_test-credential"
    )
    assert settings.runner_version == "0.2.0"
    assert settings.capabilities == [
        "asr",
        "cpu",
        "local",
    ]
    assert settings.request_timeout_seconds == 45
    assert settings.lease_seconds == 600


def test_local_runner_settings_require_credential(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    with pytest.raises(ValidationError):
        LocalRunnerSettings(_env_file=None)


def test_local_runner_settings_hide_credential(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    plaintext_credential = (
        "ovrin_runner_secret-test-credential"
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        plaintext_credential,
    )

    settings = LocalRunnerSettings(_env_file=None)

    assert plaintext_credential not in repr(settings)
    assert plaintext_credential not in str(settings)


@pytest.mark.parametrize(
    ("environment_key", "environment_value"),
    [
        (
            "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS",
            "301",
        ),
        (
            "OVRIN_RUNNER_LEASE_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_LEASE_SECONDS",
            "3601",
        ),
    ],
)
def test_local_runner_settings_reject_invalid_limits(
    monkeypatch,
    environment_key: str,
    environment_value: str,
):
    clear_runner_environment(monkeypatch)

    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )
    monkeypatch.setenv(
        environment_key,
        environment_value,
    )

    with pytest.raises(ValidationError):
        LocalRunnerSettings(_env_file=None)
