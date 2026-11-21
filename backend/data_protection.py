"""Protection of sensitive research data in the graph (D-S9, R12 of the on-top mapping).

Three tools for the ETL and the backend:

1. Field encryption. Sensitive literals (trafficker name and alias, location of the
   interview, and their raw twins) are stored as "enc:v1:<Fernet token>", the same
   format as the stored connection passwords (D-S3) but with a separate key
   (DATA_ENCRYPTION_KEY). SHACL can check that these properties hold ciphertext with
   sh:pattern "^enc:v1:".

2. Stable, non-revealing identifiers. IRIs such as :actor/{alias} would show the alias
   in plain text even when foaf:name and thinx:alias are encrypted. stable_id() builds
   the IRI part from a keyed hash (HMAC-SHA256 with ID_HMAC_KEY): the same alias always
   gives the same ID inside a deployment, so actors and places are still merged, but the
   name cannot be read from the IRI and cannot be guessed without the key.

3. Result protection. protect_results() runs over SPARQL results before they leave the
   backend. Encrypted values are decrypted only for users who may see sensitive data
   (admins and users with can_view_sensitive); for everyone else they, and values from
   restricted value lists such as coercion types, become "<restricted>".

Limitation: /api/query accepts free SPARQL, so filtering results is a safeguard, not a
full access-control layer. A user could still test for a restricted concept inside a
FILTER. Full separation needs a separate AllegroGraph repository or account for the
restricted data. Encrypted values stay safe either way, because the key never leaves
the backend.
"""
import hashlib
import hmac
import os
import re
import unicodedata

from cryptography.fernet import Fernet, InvalidToken

PREFIX = 'enc:v1:'
RESTRICTED = '<restricted>'
UNREADABLE = '<unreadable>'

# Fernet tokens are URL-safe base64 and always start with "gAAAA".
_ENCRYPTED_RE = re.compile(r'enc:v1:[A-Za-z0-9_\-]+=*')

# IRI fragments of value lists that hold special-category data (R12: coercion types).
RESTRICTED_IRI_MARKERS = tuple(
    m.strip() for m in os.getenv('RESTRICTED_IRI_MARKERS', '/coercion/').split(',') if m.strip()
)

_fernet = None


def _secret(name: str, min_length: int = 0) -> str:
    value = os.getenv(name, '').strip()
    if not value or value.lower().startswith(('change-this', 'dev-key-change')):
        raise RuntimeError(f'{name} is not set. See .env.example for how to generate it.')
    if len(value) < min_length:
        raise RuntimeError(f'{name} must be at least {min_length} characters long.')
    return value


def _cipher() -> Fernet:
    global _fernet
    if _fernet is None:
        try:
            _fernet = Fernet(_secret('DATA_ENCRYPTION_KEY').encode())
        except ValueError as e:
            raise RuntimeError('DATA_ENCRYPTION_KEY is not a valid Fernet key.') from e
    return _fernet


# ---------------------------------------------------------------------------
# 1. Field encryption
# ---------------------------------------------------------------------------

def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_value(value):
    """Encrypt one literal. None and empty strings are left alone (no triple is made)."""
    if value is None or value == '' or is_encrypted(value):
        return value
    return PREFIX + _cipher().encrypt(str(value).encode('utf-8')).decode('ascii')


def decrypt_value(value):
    """Decrypt one literal; values without the prefix are returned unchanged."""
    if not is_encrypted(value):
        return value
    try:
        return _cipher().decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')
    except InvalidToken:
        return UNREADABLE


# ---------------------------------------------------------------------------
# 2. Stable, non-revealing identifiers
# ---------------------------------------------------------------------------

def normalise(value: str) -> str:
    """Same rule as merging inside a dataset: case, accents and spacing do not matter."""
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    return ' '.join(text.split())


def stable_id(kind: str, value: str, length: int = 32) -> str:
    """Return e.g. 'actor-3f9c...' for use in an IRI such as :actor/{id}.

    kind keeps the ID spaces apart, so the same text as an actor and as a place gives
    different IDs. The result depends on ID_HMAC_KEY: keep that key stable for a
    deployment, or the same actor gets a new IRI after a re-upload.
    """
    if value is None or not str(value).strip():
        raise ValueError('stable_id needs a non-empty value')
    key = _secret('ID_HMAC_KEY', min_length=32).encode()
    message = f'{kind}\x1f{normalise(value)}'.encode('utf-8')
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f'{kind}-{digest[:length]}'


# ---------------------------------------------------------------------------
# 3. Result protection
# ---------------------------------------------------------------------------

def can_view_sensitive(user) -> bool:
    return bool(user) and bool(user.get('is_admin') or user.get('can_view_sensitive'))


def _protect_value(value, allowed: bool):
    if not isinstance(value, str):
        return value
    if PREFIX in value:
        if not allowed:
            return RESTRICTED
        # Query results arrive as N-Triples text, e.g. '"enc:v1:..."' or with a datatype.
        match = _ENCRYPTED_RE.search(value)
        return decrypt_value(match.group(0)) if match else UNREADABLE
    if not allowed and any(marker in value for marker in RESTRICTED_IRI_MARKERS):
        return RESTRICTED
    return value


def protect_results(results, user):
    """Apply the user's rights to a list of SPARQL result rows (dicts)."""
    allowed = can_view_sensitive(user)
    return [{name: _protect_value(value, allowed) for name, value in row.items()}
            for row in results or []]
