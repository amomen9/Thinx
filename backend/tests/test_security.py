"""Tests for the data-security deliverables D-S2, D-S3 and D-S5.

Run from the backend folder:
    pip install pytest
    python -m pytest tests/test_security.py -v

The tests use temporary files only; they do not need Docker, AllegroGraph or Ollama.
"""
import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

TEST_ENV = {
    'SECRET_KEY': 'test-secret-key-0123456789abcdef',
    'CONNECTION_ENCRYPTION_KEY': Fernet.generate_key().decode(),
}


def _stub_franz():
    """The AllegroGraph client library is only needed for real database calls."""
    if 'franz' in sys.modules:
        return
    names = ['franz', 'franz.openrdf', 'franz.openrdf.connect', 'franz.openrdf.sail',
             'franz.openrdf.sail.allegrographserver', 'franz.openrdf.query', 'franz.openrdf.query.query']
    for name in names:
        sys.modules[name] = types.ModuleType(name)
    sys.modules['franz.openrdf.connect'].ag_connect = lambda *a, **k: None
    sys.modules['franz.openrdf.sail.allegrographserver'].AllegroGraphServer = object
    sys.modules['franz.openrdf.query.query'].QueryLanguage = object


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    _stub_franz()
    for mod in ('config', 'secret_store', 'models', 'app'):
        sys.modules.pop(mod, None)
    app_module = importlib.import_module('app')
    models = importlib.import_module('models')
    # isolated storage for this test
    app_module.connection_manager = models.ConnectionManager(tmp_path / 'connections.json')
    app_module.user_manager = models.UserManager(tmp_path / 'users.json')
    app_module.app.config['TESTING'] = True
    return app_module, models, tmp_path


def _login_admin(app_module):
    app_module.user_manager.create_user('alice', 'a-long-test-password')
    users = app_module.user_manager._load_users()
    users[0]['is_admin'] = True
    app_module.user_manager._save_users(users)
    client = app_module.app.test_client()
    res = client.post('/api/login', json={'username': 'alice', 'password': 'a-long-test-password'})
    assert res.status_code == 200, res.get_json()
    token = res.get_json()['access_token']
    return client, {'Authorization': f'Bearer {token}'}, users[0]['id']


# ---------------------------------------------------------------- D-S2

@pytest.mark.parametrize('missing', ['SECRET_KEY', 'CONNECTION_ENCRYPTION_KEY'])
def test_backend_refuses_to_start_without_secret(monkeypatch, missing):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing)
    sys.modules.pop('config', None)
    with pytest.raises(RuntimeError, match=missing):
        importlib.import_module('config')


def test_placeholder_secret_is_rejected(monkeypatch):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('SECRET_KEY', 'change-this-to-a-secure-random-string')
    sys.modules.pop('config', None)
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        importlib.import_module('config')


def test_no_hardcoded_default_passwords_in_code():
    repo = BACKEND.parent
    files = [*repo.glob('*.py'), *BACKEND.glob('*.py'), repo / 'docker-compose.yml']
    for path in files:
        text = path.read_text(errors='ignore')
        assert 'admin123' not in text, f'default password left in {path.name}'


# ---------------------------------------------------------------- D-S3

def test_connection_password_is_encrypted_on_disk(backend):
    app_module, models, tmp_path = backend
    conn = models.Connection(name='repo', host='h', repository='r', username='u',
                             password='plain-secret', user_id='x')
    app_module.connection_manager.add_connection(conn)
    stored = json.loads((tmp_path / 'connections.json').read_text())[0]['password']
    assert stored.startswith('enc:v1:') and 'plain-secret' not in stored
    # decrypted again in memory for the AllegroGraph client
    assert app_module.connection_manager.get_connection(conn.id)['password'] == 'plain-secret'


def test_legacy_plaintext_password_is_migrated(backend):
    _, models, tmp_path = backend
    path = tmp_path / 'legacy.json'
    path.write_text(json.dumps([{'id': '1', 'name': 'old', 'password': 'old-secret', 'user_id': 'x'}]))
    manager = models.ConnectionManager(path)
    assert json.loads(path.read_text())[0]['password'].startswith('enc:v1:')
    assert manager.get_connection('1')['password'] == 'old-secret'


def test_api_never_returns_connection_passwords(backend):
    app_module, models, _ = backend
    client, headers, user_id = _login_admin(app_module)
    conn = models.Connection(name='repo', host='h', repository='r', username='u',
                             password='plain-secret', user_id=user_id)
    app_module.connection_manager.add_connection(conn)

    for url in ('/api/connections', f'/api/connections/{conn.id}', '/api/connections/active'):
        res = client.get(url, headers=headers)
        assert res.status_code == 200, (url, res.get_json())
        assert 'plain-secret' not in res.get_data(as_text=True), url
        assert '"password"' not in res.get_data(as_text=True), url


def test_empty_password_on_edit_keeps_stored_password(backend):
    app_module, models, _ = backend
    conn = models.Connection(name='repo', password='plain-secret', user_id='x')
    app_module.connection_manager.add_connection(conn)
    app_module.connection_manager.update_connection(conn.id, {'name': 'renamed', 'password': ''})
    updated = app_module.connection_manager.get_connection(conn.id)
    assert updated['name'] == 'renamed' and updated['password'] == 'plain-secret'


# ---------------------------------------------------------------- D-S5

def test_intermediate_files_are_removed(backend, tmp_path):
    app_module, _, _ = backend
    for name in app_module.INTERMEDIATE_FILES:
        (tmp_path / name).write_text('victim data')
    (tmp_path / 'keep_me.txt').write_text('not intermediate')
    removed = app_module.remove_intermediate_files(tmp_path)
    assert sorted(removed) == sorted(app_module.INTERMEDIATE_FILES)
    assert not any((tmp_path / name).exists() for name in app_module.INTERMEDIATE_FILES)
    assert (tmp_path / 'keep_me.txt').exists()


def test_intermediate_files_kept_when_configured(backend, tmp_path, monkeypatch):
    app_module, _, _ = backend
    monkeypatch.setattr(app_module.config, 'KEEP_INTERMEDIATE_FILES', True)
    (tmp_path / 'victims.json').write_text('victim data')
    assert app_module.remove_intermediate_files(tmp_path) == []
    assert (tmp_path / 'victims.json').exists()
