import hashlib
import hmac
import secrets


REGISTRATION_TOKEN_PREFIX = "ovrin_reg_"
RUNNER_CREDENTIAL_PREFIX = "ovrin_runner_"
SECRET_ENTROPY_BYTES = 32


def _generate_secret(prefix: str) -> str:
    """Generate a high-entropy secret that can be displayed only once."""
    return f"{prefix}{secrets.token_urlsafe(SECRET_ENTROPY_BYTES)}"


def _hash_secret(secret: str, purpose: str) -> str:
    """
    Return a deterministic SHA-256 digest for a high-entropy secret.

    The purpose value provides domain separation so that registration-token
    hashes and runner-credential hashes cannot be used interchangeably.
    """
    if not secret:
        raise ValueError("Secret must not be empty.")

    digest_input = f"ovrin:{purpose}:{secret}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def generate_registration_token() -> str:
    return _generate_secret(REGISTRATION_TOKEN_PREFIX)


def hash_registration_token(token: str) -> str:
    return _hash_secret(token, purpose="runner-registration")


def verify_registration_token(
    token: str,
    expected_hash: str,
) -> bool:
    if not token or not expected_hash:
        return False

    actual_hash = hash_registration_token(token)
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_runner_credential() -> str:
    return _generate_secret(RUNNER_CREDENTIAL_PREFIX)


def hash_runner_credential(credential: str) -> str:
    return _hash_secret(credential, purpose="runner-credential")


def verify_runner_credential(
    credential: str,
    expected_hash: str,
) -> bool:
    if not credential or not expected_hash:
        return False

    actual_hash = hash_runner_credential(credential)
    return hmac.compare_digest(actual_hash, expected_hash)
