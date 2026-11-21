"""Tests for backend/data_protection.py (D-S9: sensitive data in the graph).

Run from the backend folder:
    python -m pytest tests/test_data_protection.py -v
"""
import importlib
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def dp(monkeypatch):
    monkeypatch.setenv('DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('ID_HMAC_KEY', 'k' * 40)
    import data_protection
    return importlib.reload(data_protection)


VIEWER = {'id': 'u1', 'is_admin': False}
RESEARCHER = {'id': 'u2', 'is_admin': False, 'can_view_sensitive': True}
ADMIN = {'id': 'u3', 'is_admin': True}


def test_encrypt_roundtrip_and_format(dp):
    token = dp.encrypt_value('Example Alias')
    assert token.startswith('enc:v1:gAAAA')          # what the SHACL sh:pattern checks
    assert 'Example' not in token
    assert dp.decrypt_value(token) == 'Example Alias'


def test_encrypt_leaves_empty_and_encrypted_values(dp):
    assert dp.encrypt_value(None) is None
    assert dp.encrypt_value('') == ''
    token = dp.encrypt_value('x')
    assert dp.encrypt_value(token) == token           # no double encryption


def test_wrong_key_gives_unreadable(dp, monkeypatch):
    token = dp.encrypt_value('secret')
    monkeypatch.setenv('DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    dp2 = importlib.reload(dp)
    assert dp2.decrypt_value(token) == '<unreadable>'


def test_stable_id_is_stable_and_normalised(dp):
    a = dp.stable_id('actor', 'Example  Alias')
    assert a == dp.stable_id('actor', ' example alias ')
    assert a.startswith('actor-') and len(a) == len('actor-') + 32
    assert 'example' not in a.lower().replace('actor-', '')


def test_stable_id_separates_kinds_and_values(dp):
    assert dp.stable_id('actor', 'X') != dp.stable_id('place', 'X')
    assert dp.stable_id('actor', 'X') != dp.stable_id('actor', 'Y')


def test_stable_id_depends_on_key(dp, monkeypatch):
    first = dp.stable_id('actor', 'X')
    monkeypatch.setenv('ID_HMAC_KEY', 'z' * 40)
    assert dp.stable_id('actor', 'X') != first


def test_stable_id_rejects_short_key_and_empty_value(dp, monkeypatch):
    with pytest.raises(ValueError):
        dp.stable_id('actor', '  ')
    monkeypatch.setenv('ID_HMAC_KEY', 'short')
    with pytest.raises(RuntimeError):
        dp.stable_id('actor', 'X')


def test_missing_key_fails_clearly(dp, monkeypatch):
    monkeypatch.delenv('DATA_ENCRYPTION_KEY')
    dp2 = importlib.reload(dp)
    with pytest.raises(RuntimeError):
        dp2.encrypt_value('x')


def _rows(dp):
    token = dp.encrypt_value('Example Alias')
    return [{
        'actor': '<https://example.org/dataset/1/v1/actor/actor-abc>',
        'alias': f'"{token}"',                                            # N-Triples literal
        'coercion': '<https://example.org/thinx/coercion/detention>',
        'domain': '<https://example.org/incident-domains.ttl#humanTrafficking>',
        'missing': None,
    }]


def test_viewer_sees_restricted(dp):
    row = dp.protect_results(_rows(dp), VIEWER)[0]
    assert row['alias'] == '<restricted>'
    assert row['coercion'] == '<restricted>'
    assert row['domain'].endswith('humanTrafficking>')                   # not restricted
    assert row['actor'].endswith('actor-abc>')                           # IRI reveals nothing
    assert row['missing'] is None


@pytest.mark.parametrize('user', [RESEARCHER, ADMIN])
def test_authorised_user_sees_decrypted(dp, user):
    row = dp.protect_results(_rows(dp), user)[0]
    assert row['alias'] == 'Example Alias'
    assert row['coercion'].endswith('/coercion/detention>')


def test_no_user_is_treated_as_viewer(dp):
    assert dp.protect_results(_rows(dp), None)[0]['alias'] == '<restricted>'
