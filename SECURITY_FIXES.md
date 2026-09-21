# Security and quality fixes on branch Ali

**Branch:** Ali of amomen9/Thinx (fork of VODAN-Development/Thinx)
**Base commit:** 0b4cd0d
**Date:** 2026-09-20
**Author:** Ali Momen, DSIP FieldLab Team Thinx

These changes close the findings of the assessment of 2026-09-19. Three of the critical
findings were reproduced on a running deployment before the work started, and the same
checks were repeated afterwards. Nothing here has been proposed to the upstream project
yet; this branch exists so the FieldLab can review the work first.

Finding identifiers (C1, H2, M4, and so on) refer to **Thinx_Assessment_Findings.md**.

---

## Verified before the fix, on the running deployment

    /api/connections    HTTP 200 without any credentials
    /api/admin/users    HTTP 200 without any credentials, full user list returned
    GET /api/connections returned the stored database password in clear text
    POST /api/login with admin / admin succeeded

## Verified after the fix, on the same deployment

    /api/connections    HTTP 401 without a session
    /api/admin/users    HTTP 401 without a session, 403 for a signed-in non-administrator
    GET /api/connections with a valid session returns no password field at all
    POST /api/login with admin / admin fails: the account does not exist any more

---

## What changed, finding by finding

### C1 - No authentication on any API endpoint. Fixed.

**backend/auth.py** (new) holds sessions, the login and administrator decorators, and a
**before_request** guard that closes every route by default. A route is reachable without
a session only when it carries the **@public** decorator: health, session, register, login
and logout. Any endpoint added later is protected automatically, which is what stops this
finding from coming back.

**backend/app.py** configures the session (signed, HttpOnly cookie, lifetime from
**SESSION_TIMEOUT**), marks the five public routes, and requires administrator rights on
the user-administration routes. CORS now allows credentials and takes its origin list from
**CORS_ORIGINS** instead of two hardcoded localhost values.

**frontend/src/services/api.js** sends the session cookie (**withCredentials**) and sends
the user back to the login screen on a 401. **frontend/src/App.vue** asks the server who is
signed in instead of trusting **localStorage**, and logging out now destroys the session on
the server. **Login.vue** and **Register.vue** used bare axios against a hardcoded
**http://localhost:5000**, which both ignored **VITE_API_URL** and dropped the session
cookie; they now use the shared API client.

### C2 - Default administrator admin / admin. Fixed.

**backend/models.py** no longer writes a built-in account when the user store is created.
The store starts empty and the first account that registers becomes the administrator, so
no installation ships with a password that is published in a repository. Set
**ALLOW_REGISTRATION=false** after that first account exists.

### C3 - Database passwords served by an open endpoint. Fixed.

**public_connection()** in **backend/models.py** strips the password, and every endpoint in
**backend/app.py** that returns a connection now passes through it. The password is still
stored so the backend can connect; it is never sent to a client. Encrypting it at rest is
still open, and the README now says so instead of claiming the opposite.

### H1 - Credentials committed to the repository. Fixed in the working tree, open in history.

Removed: the generated password in **push_to_allegrograph.py**, the three admin/admin123
repositories in **federated_query.py**, and the hosted endpoint plus a second live-looking
password in **list_repos.py** (that one had been missed on the first pass because the search
was case-sensitive; it is the reason the sweep is now part of the checklist). Every script
reads its credentials from the environment and exits with a clear message rather than
falling back to a default.

**Still open, and it needs the repository owner:** the values remain in the git history.
They must be rotated wherever they were used, and the history rewritten (git filter-repo or
BFG) or the repository replaced. Rotation matters more than the rewrite.

### H2 - Flask debug mode exposed. Fixed.

**backend/app.py** reads the debug flag from the environment and refuses it unless
**FLASK_ENV** is development, so the Werkzeug debugger cannot be reached on a normal
deployment. **docker-compose.yml** now defaults to **FLASK_ENV=production** and
**FLASK_DEBUG=0**. Running the API behind gunicorn instead of the Flask development server
is still open.

### H3 - Unauthenticated notebook execution. Fixed.

**/api/run-notebook** now takes a name from a two-entry allowlist, resolves the path and
verifies it stays inside the workspace, and no longer returns filesystem paths in its
errors. It also sits behind the login guard.

### H4 - Weak password hashing. Fixed.

PBKDF2-HMAC-SHA256, 600000 iterations, 16 random bytes of salt per user, constant-time
comparison, all from the standard library so no new dependency. Old bare SHA-256 hashes
still verify and are rewritten in the new format at the next successful login. The minimum
password length is now 12.

### H5 - 89 known advisories in the pinned dependencies. Fixed.

All pins moved to versions with no advisory in the OSV.dev database on 2026-09-20: Flask
3.1.3, Werkzeug 3.1.8, flask-cors 6.0.5, requests 2.34.2, urllib3 2.8.0, nbconvert 7.17.1,
python-dotenv 1.2.3, rdflib 7.6.0, pandas 2.3.3, openpyxl 3.1.5, jupyter 1.1.1, pycurl
7.48.0; axios 1.20.0, vue 3.5.43, vue-router 4.6.4, vite 7.3.6, @vitejs/plugin-vue 6.0.9.
Vite 7 needs a newer Node, so the frontend image moved to node:22-alpine. The Ollama image
is pinned to a version instead of **latest**. Automated scanning in CI is still open.

### H6 - No transport encryption. Partly addressed.

Not solved in code, because it belongs in front of the stack. What changed: published ports
bind to **127.0.0.1** by default (**BIND_HOST**), so the intended deployment is behind a
reverse proxy or an SSH tunnel, and **SESSION_COOKIE_SECURE** exists for the moment TLS is
in place. Certificate validation for the FAIR Data Point is still disabled and still needs
the certificate chain fixed.

### M3 - Root containers, published ports. Partly fixed.

Ports now bind to the loopback interface by default. The containers still run as root: both
services bind-mount the project directory, so switching users needs a UID mapping decision
that changes how the pipeline writes its output. Left open deliberately rather than shipped
half-done.

### M4 - Data can slip into the repository. Fixed.

**.gitignore** now also covers **uploads/**, **data.xlsx** and **.orig** files. Stripping
notebook outputs before commit (nbstripout) is recommended but not yet wired in.

### M6 - Internal errors returned to the client. Fixed for the global handler.

**safe_error()** logs the exception server-side and returns a generic message unless the
service runs in development mode. The global handler and the touched endpoints use it; the
remaining per-endpoint handlers still pass exception text and are a follow-up.

### L1 - Documentation that did not match the code. Fixed.

The compose file no longer carries a password at all, so the admin1233 and admin123
mismatch is gone: **AGRAPH_SUPER_PASSWORD** and **SECRET_KEY** are required in **.env** and
the stack refuses to start without them. **start.sh** now uses the compose plugin, selects
a profile (without one it started nothing) and prints the real URLs. **check-setup.sh**
checks for the compose plugin and for port 8080 rather than port 80. The operator docs were
corrected the same way.

### L2 - Two configuration systems. Partly fixed.

CORS origins, registration, password length, session lifetime, bind host, debug and the
secret key are now read from the environment and passed through the compose file, and
**.env.example** documents only what is actually read. Making **backend/config.py** the
single source for the rest is a follow-up.

### L5 - Hot reload broken. Fixed.

The HMR client port was pinned to 80 while the service is published on 8080. It now follows
the page, with **VITE_HMR_CLIENT_PORT** as an override.

### L7 - The database healthcheck could never pass. Fixed.

The compose healthcheck called **curl** inside an image that has no curl, so the database
container reported unhealthy forever (854 consecutive failures on the test deployment). It
now uses a shell TCP probe.

### M2 - Documentation claiming protections that did not exist. Fixed.

The claims that passwords are encrypted, that the platform protects data with encryption
and access controls, and that everything is GDPR compliant have been replaced with what is
actually true, including a pointer to this file.

---

## Still open after this branch

| Finding | What is needed |
|---|---|
| H1 (history) | Rotate the exposed credentials, then rewrite or replace the repository history. Needs the owner. |
| H6 | TLS in front of the stack; fix the FAIR Data Point certificate instead of disabling validation. |
| M1 | DPIA, access logging, retention and erasure. A FieldLab deliverable, not a code change. |
| M3 | Non-root containers, which needs a UID mapping decision for the bind mounts. |
| M5 | Per-user upload isolation; every upload still lands on one shared data.xlsx. |
| M7 | Encryption at rest for the database volume and for backups. |
| L3, L4, L6 | Regenerate the admin guide, add CI and tests and a licence, move the pipeline out of notebooks. |

## How to run this branch

    cp .env.example .env
    # set SECRET_KEY and AGRAPH_SUPER_PASSWORD, then:
    ./start.sh

Open http://localhost:8080 and register. The first account becomes the administrator; set
**ALLOW_REGISTRATION=false** afterwards. An existing deployment keeps its data: old accounts
still work and their password hashes are upgraded at the next login, but the old admin/admin
account must be removed by hand if it is still present.
