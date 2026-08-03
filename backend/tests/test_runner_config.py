import pytest
from pydantic import ValidationError

from app.runner_config import LocalRunnerSettings


LEGACY_RUNNER_ENVIRONMENT_KEYS = (
    "OVRIN_RUNNER_API_URL",
    "OVRIN_RUNNER_CREDENTIAL",
    "OVRIN_RUNNER_VERSION",
    "OVRIN_RUNNER_CAPABILITIES",
    "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS",
    "OVRIN_RUNNER_LEASE_SECONDS",
    "OVRIN_RUNNER_POLL_INTERVAL_SECONDS",
    "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
    "OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS",
    "OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS",
    "OVRIN_RUNNER_ASR_PROVIDER",
    "OVRIN_RUNNER_ASR_MODEL",
    "OVRIN_RUNNER_ASR_DEVICE",
    "OVRIN_RUNNER_ASR_COMPUTE_TYPE",
)

HETREN_RUNNER_ENVIRONMENT_KEYS = tuple(
    key.replace("OVRIN_", "HETREN_", 1)
    for key in LEGACY_RUNNER_ENVIRONMENT_KEYS
)

RUNNER_ENVIRONMENT_KEYS = (
    *HETREN_RUNNER_ENVIRONMENT_KEYS,
    *LEGACY_RUNNER_ENVIRONMENT_KEYS,
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
    monkeypatch.setenv(
        "OVRIN_RUNNER_POLL_INTERVAL_SECONDS",
        "7.5",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
        "120",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS",
        "3",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS",
        "1800",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_ASR_PROVIDER",
        " faster-whisper ",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_ASR_MODEL",
        " small.en ",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_ASR_DEVICE",
        " CUDA ",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_ASR_COMPUTE_TYPE",
        " FLOAT16 ",
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
    assert settings.poll_interval_seconds == 7.5
    assert (
        settings.lease_renewal_interval_seconds
        == 120
    )
    assert settings.control_poll_interval_seconds == 3
    assert settings.execution_timeout_seconds == 1800
    assert settings.asr_provider == "faster_whisper"
    assert settings.asr_model == "small.en"
    assert settings.asr_device == "cuda"
    assert settings.asr_compute_type == "float16"


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
        (
            "OVRIN_RUNNER_POLL_INTERVAL_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_POLL_INTERVAL_SECONDS",
            "301",
        ),
        (
            "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
            "1801",
        ),
        (
            "OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS",
            "301",
        ),
        (
            "OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS",
            "0",
        ),
        (
            "OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS",
            "86401",
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

def test_local_runner_settings_require_renewal_before_expiry(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_SECONDS",
        "60",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
        "60",
    )

    with pytest.raises(ValidationError):
        LocalRunnerSettings(_env_file=None)



def test_local_runner_settings_require_control_polling_before_renewal(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_SECONDS",
        "120",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS",
        "30",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS",
        "30",
    )

    with pytest.raises(ValidationError):
        LocalRunnerSettings(_env_file=None)



def test_local_runner_settings_use_safe_asr_defaults(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)
    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )

    settings = LocalRunnerSettings(_env_file=None)

    assert settings.asr_provider == "mock_local"
    assert settings.asr_model == (
        "mock-asr-foundation"
    )
    assert settings.asr_device == "cpu"
    assert settings.asr_compute_type == "int8"


@pytest.mark.parametrize(
    ("environment_key", "environment_value"),
    [
        ("OVRIN_RUNNER_ASR_PROVIDER", "unknown"),
        ("OVRIN_RUNNER_ASR_MODEL", "   "),
        ("OVRIN_RUNNER_ASR_DEVICE", "   "),
        ("OVRIN_RUNNER_ASR_COMPUTE_TYPE", "   "),
    ],
)
def test_local_runner_settings_reject_invalid_asr_configuration(
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


def test_local_runner_settings_load_hetren_environment(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)

    environment = {
        "HETREN_RUNNER_API_URL": "https://hetren.example.com/",
        "HETREN_RUNNER_CREDENTIAL": (
            "hetren_runner_test-credential"
        ),
        "HETREN_RUNNER_VERSION": " 0.2.0 ",
        "HETREN_RUNNER_CAPABILITIES": (
            '[" ASR ", "cpu", "asr", "local"]'
        ),
        "HETREN_RUNNER_REQUEST_TIMEOUT_SECONDS": "45",
        "HETREN_RUNNER_LEASE_SECONDS": "600",
        "HETREN_RUNNER_POLL_INTERVAL_SECONDS": "7.5",
        "HETREN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS": "120",
        "HETREN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS": "3",
        "HETREN_RUNNER_EXECUTION_TIMEOUT_SECONDS": "1800",
        "HETREN_RUNNER_ASR_PROVIDER": " faster-whisper ",
        "HETREN_RUNNER_ASR_MODEL": " small.en ",
        "HETREN_RUNNER_ASR_DEVICE": " CUDA ",
        "HETREN_RUNNER_ASR_COMPUTE_TYPE": " FLOAT16 ",
    }

    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    settings = LocalRunnerSettings(_env_file=None)

    assert settings.api_base_url == "https://hetren.example.com"
    assert (
        settings.credential.get_secret_value()
        == "hetren_runner_test-credential"
    )
    assert settings.runner_version == "0.2.0"
    assert settings.capabilities == ["asr", "cpu", "local"]
    assert settings.request_timeout_seconds == 45
    assert settings.lease_seconds == 600
    assert settings.poll_interval_seconds == 7.5
    assert settings.lease_renewal_interval_seconds == 120
    assert settings.control_poll_interval_seconds == 3
    assert settings.execution_timeout_seconds == 1800
    assert settings.asr_provider == "faster_whisper"
    assert settings.asr_model == "small.en"
    assert settings.asr_device == "cuda"
    assert settings.asr_compute_type == "float16"


def test_local_runner_settings_accept_legacy_ovrin_environment(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)
    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_test-credential",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_API_URL",
        "https://legacy.example.com/",
    )

    settings = LocalRunnerSettings(_env_file=None)

    assert settings.api_base_url == "https://legacy.example.com"
    assert (
        settings.credential.get_secret_value()
        == "ovrin_runner_test-credential"
    )


def test_hetren_runner_environment_takes_precedence(
    monkeypatch,
):
    clear_runner_environment(monkeypatch)
    monkeypatch.setenv(
        "HETREN_RUNNER_CREDENTIAL",
        "hetren_runner_primary-credential",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_CREDENTIAL",
        "ovrin_runner_legacy-credential",
    )
    monkeypatch.setenv(
        "HETREN_RUNNER_API_URL",
        "https://hetren.example.com/",
    )
    monkeypatch.setenv(
        "OVRIN_RUNNER_API_URL",
        "https://legacy.example.com/",
    )

    settings = LocalRunnerSettings(_env_file=None)

    assert settings.api_base_url == "https://hetren.example.com"
    assert (
        settings.credential.get_secret_value()
        == "hetren_runner_primary-credential"
    )
