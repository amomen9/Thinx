"""Encryption of stored connection passwords (D-S3).

Connection passwords are written to data/connections.json encrypted with Fernet
(AES-128-CBC + HMAC-SHA256, from the `cryptography` package). The key comes from
the CONNECTION_ENCRYPTION_KEY environment variable and never touches the disk
next to the data.

Stored values look like "enc:v1:<token>". Values without that prefix are legacy
plaintext passwords from before this change: they are still read correctly and
are encrypted the next time the connections file is saved.
"""
from cryptography.fernet import Fernet, InvalidToken

import config

PREFIX = 'enc:v1:'

try:
    _fernet = Fernet(config.CONNECTION_ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as exc:
    raise RuntimeError(
        'CONNECTION_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: '
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    ) from exc


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_secret(value):
    """Encrypt a plaintext secret; empty values and already encrypted values are kept."""
    if not value or is_encrypted(value):
        return value
    return PREFIX + _fernet.encrypt(str(value).encode()).decode()


def decrypt_secret(value):
    """Decrypt a stored secret; legacy plaintext values are returned unchanged."""
    if not is_encrypted(value):
        return value
    try:
        return _fernet.decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError(
            'A stored connection password cannot be decrypted. Was CONNECTION_ENCRYPTION_KEY changed? '
            'Restore the old key or re-enter the connection password.'
        ) from exc
