import pytest

from app.runner_security import (
    REGISTRATION_TOKEN_PREFIX,
    RUNNER_CREDENTIAL_PREFIX,
    generate_registration_token,
    generate_runner_credential,
    hash_registration_token,
    hash_runner_credential,
    verify_registration_token,
    verify_runner_credential,
)


def test_registration_tokens_are_prefixed_and_unique():
    first_token = generate_registration_token()
    second_token = generate_registration_token()

    assert first_token.startswith(REGISTRATION_TOKEN_PREFIX)
    assert second_token.startswith(REGISTRATION_TOKEN_PREFIX)
    assert first_token != second_token


def test_runner_credentials_are_prefixed_and_unique():
    first_credential = generate_runner_credential()
    second_credential = generate_runner_credential()

    assert first_credential.startswith(RUNNER_CREDENTIAL_PREFIX)
    assert second_credential.startswith(RUNNER_CREDENTIAL_PREFIX)
    assert first_credential != second_credential


def test_registration_token_hash_is_deterministic_and_not_plaintext():
    token = generate_registration_token()

    first_hash = hash_registration_token(token)
    second_hash = hash_registration_token(token)

    assert first_hash == second_hash
    assert first_hash != token
    assert len(first_hash) == 64


def test_runner_credential_hash_is_deterministic_and_not_plaintext():
    credential = generate_runner_credential()

    first_hash = hash_runner_credential(credential)
    second_hash = hash_runner_credential(credential)

    assert first_hash == second_hash
    assert first_hash != credential
    assert len(first_hash) == 64


def test_registration_token_verification_rejects_wrong_token():
    token = generate_registration_token()
    token_hash = hash_registration_token(token)

    assert verify_registration_token(token, token_hash) is True
    assert (
        verify_registration_token(
            generate_registration_token(),
            token_hash,
        )
        is False
    )


def test_runner_credential_verification_rejects_wrong_credential():
    credential = generate_runner_credential()
    credential_hash = hash_runner_credential(credential)

    assert verify_runner_credential(credential, credential_hash) is True
    assert (
        verify_runner_credential(
            generate_runner_credential(),
            credential_hash,
        )
        is False
    )


def test_registration_and_runner_hashes_are_domain_separated():
    shared_secret = "same-high-entropy-secret"

    registration_hash = hash_registration_token(shared_secret)
    credential_hash = hash_runner_credential(shared_secret)

    assert registration_hash != credential_hash


@pytest.mark.parametrize(
    "hash_function",
    [
        hash_registration_token,
        hash_runner_credential,
    ],
)
def test_hash_functions_reject_empty_secrets(hash_function):
    with pytest.raises(ValueError, match="must not be empty"):
        hash_function("")


@pytest.mark.parametrize(
    ("verify_function", "secret", "expected_hash"),
    [
        (verify_registration_token, "", "abc"),
        (verify_registration_token, "token", ""),
        (verify_runner_credential, "", "abc"),
        (verify_runner_credential, "credential", ""),
    ],
)
def test_verification_rejects_missing_values(
    verify_function,
    secret,
    expected_hash,
):
    assert verify_function(secret, expected_hash) is False
