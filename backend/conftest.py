"""Shared test setup for the backend tests (test_auth.py and tests/test_security.py).

Sets test-only secrets before app/config are imported (config refuses to start
without them) and stubs the AllegroGraph client, which the tests never call.
"""
import os
import sys
import types

from cryptography.fernet import Fernet

os.environ.setdefault('SECRET_KEY', 'test-only-secret-not-for-production-123456789012345')
os.environ.setdefault('CONNECTION_ENCRYPTION_KEY', Fernet.generate_key().decode())
os.environ.setdefault('DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
os.environ.setdefault('ID_HMAC_KEY', 'test-only-hmac-key-not-for-production-0123456789')

if 'franz' not in sys.modules:
    for name in ['franz', 'franz.openrdf', 'franz.openrdf.connect', 'franz.openrdf.sail',
                 'franz.openrdf.sail.allegrographserver', 'franz.openrdf.query',
                 'franz.openrdf.query.query']:
        sys.modules[name] = types.ModuleType(name)
    sys.modules['franz.openrdf.connect'].ag_connect = lambda *a, **k: None
    sys.modules['franz.openrdf.sail.allegrographserver'].AllegroGraphServer = object
    sys.modules['franz.openrdf.query.query'].QueryLanguage = object
