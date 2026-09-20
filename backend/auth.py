"""
Server-side authentication for the Thinx API.

Before this module existed the API had no access control at all: the only check in
the product was a key in the browser's localStorage, so any client that could reach
port 5000 could read every connection, every query result and the user list
(assessment finding C1).

Every route is now closed by default. A route is reachable without a session only if
it is decorated with @public. Routes that administer users additionally require
@admin_required.
"""
import functools
import os
import secrets
from datetime import timedelta

from flask import jsonify, request, session

SESSION_USER_KEY = 'user_id'
SESSION_ADMIN_KEY = 'is_admin'
SESSION_NAME_KEY = 'username'

# Paths that must stay reachable without a session.
PUBLIC_ENDPOINTS = set()


def configure(app):
    """Apply session and cookie settings to the Flask app."""
    secret = os.getenv('SECRET_KEY')
    if not secret:
        if os.getenv('FLASK_ENV', 'production') == 'production':
            raise RuntimeError(
                "SECRET_KEY is not set. Generate one with "
                "'python -c \"import secrets; print(secrets.token_hex(32))\"' and put it in .env"
            )
        secret = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY not set; using a temporary key (development only). "
                           "Sessions will be invalidated on restart.")

    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv('SESSION_COOKIE_SAMESITE', 'Lax'),
        SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true',
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=int(os.getenv('SESSION_TIMEOUT', 3600))),
    )
    return app


def public(view):
    """Mark a view as reachable without a session."""
    PUBLIC_ENDPOINTS.add(view.__name__)
    view.__thinx_public__ = True
    return view


def current_user():
    """The signed-in user as stored in the session, or None."""
    if SESSION_USER_KEY not in session:
        return None
    return {
        'id': session[SESSION_USER_KEY],
        'username': session.get(SESSION_NAME_KEY),
        'is_admin': session.get(SESSION_ADMIN_KEY, False),
    }


def start_session(user):
    """Record a successful login."""
    session.clear()
    session.permanent = True
    session[SESSION_USER_KEY] = user['id']
    session[SESSION_NAME_KEY] = user.get('username')
    session[SESSION_ADMIN_KEY] = bool(user.get('is_admin'))


def end_session():
    session.clear()


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        if not user['is_admin']:
            return jsonify({'success': False, 'error': 'Administrator rights required'}), 403
        return view(*args, **kwargs)
    return wrapper


def install_guard(app):
    """Close every route by default, including any added later.

    A before_request hook is used rather than per-route decorators alone, so that a
    new endpoint is protected unless its author deliberately marks it @public. This
    is what keeps finding C1 from coming back.
    """
    @app.before_request
    def _require_session():
        if request.method == 'OPTIONS':
            return None
        endpoint = request.endpoint
        if endpoint is None or endpoint == 'static':
            return None
        view = app.view_functions.get(endpoint)
        if view is not None and getattr(view, '__thinx_public__', False):
            return None
        if current_user() is None:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return None

    return app
