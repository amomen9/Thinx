# Thinx platform - assessment of issues to solve

**Scope:** VODAN-Development/Thinx, commit **0b4cd0d** (2026-07-15, the current tip of **main**), plus a working deployment of that commit on a local Linux VM (Docker Compose, profile **full**, mock dataset **Mock data/DT01.xlsx** imported).

**Date of assessment:** 2026-09-19
**Assessor:** Ali Momen (DSIP FieldLab, Team Thinx), assisted by Claude Opus 5 - see **Thinx_AI_Usage_Log.md**
**Method:** passive source-code review, configuration review, dependency vulnerability lookup against the OSV.dev database, and first-hand experience of deploying the stack. No intrusive or active security testing was performed against any server.

**Severity scale**

| Level | Meaning |
|---|---|
| Critical | Exploitable by anyone who can reach the application, with direct access to research data |
| High | Serious weakness, exploitable with little effort or under realistic conditions |
| Medium | Real risk, but needs a precondition, or the impact is limited or indirect |
| Low | Quality, maintainability or documentation defect that costs time and causes mistakes |

**Totals:** 3 Critical, 6 High, 8 Medium, 7 Low (24 findings).

**Update of 2026-09-20.** The system owner granted SSH access to the virtual machine and written
authorization to test actively against it, and asked for the fixes to be implemented on the fork
branch **Ali**. Three things follow from that:

1. The critical findings were **reproduced on the running deployment** before any change, and one
   new finding was added (**L7**, the database healthcheck that could never pass).
2. **13 findings are now closed and 4 are narrowed** by the commit on branch **Ali**. See
   **SECURITY_FIXES.md** in that branch for the change-by-change report.
3. The same probes were repeated afterwards. The results are in the verification section below.

**Update of 2026-09-21.** Querying the imported mock dataset in AllegroGraph showed that no victim
had an age. The cause is a new finding, **M8**, fixed on branch **Ali** the same day.

| Status | Findings |
|---|---|
| Closed | C1, C2, C3, H2, H3, H4, H5, M2, M4, M6, M8, L1, L5, L7 |
| Partly closed | H1 (code clean, git history still exposed), H6, M3, L2 |
| Open | M1, M5, M7, L3, L4, L6 |

---

## Verification on the running system

Deployment: the same virtual machine, the same Docker volumes, before and after the change.
The checks below are HTTP requests sent from the machine itself, with no credentials unless stated.

| Check | Before | After |
|---|---|---|
| GET /api/connections, no credentials | HTTP 200 with data | HTTP 401 |
| GET /api/admin/users, no credentials | HTTP 200, full user list | HTTP 401 |
| GET /api/admin/users, ordinary account | n/a, there was no session | HTTP 403 |
| Password field in a connection response | present, clear text | absent |
| Login with admin / admin | succeeded | account is not created on a new installation |
| Stored hash of that account | bare SHA-256 | pbkdf2_sha256, 600000 iterations, per-user salt |
| POST /api/run-notebook with ../../etc/evil.ipynb | accepted the path | HTTP 400, name not on the allowlist |
| Registration with a 6-character password | accepted | rejected, minimum is 12 |
| Session after logout | n/a | HTTP 401 |
| Werkzeug debugger | on, FLASK_DEBUG=1 | off, FLASK_ENV=production |
| Database container health | unhealthy, 854 consecutive failures | healthy |

**Still true on the deployed instance:** the **admin / admin** account created by the old code is
still in the data volume and still works. Removing the default stops new installations from having
one; it does not delete an account that already exists. Change or delete it on any instance that has
been running.

---

## A. Access control and authentication

### C1 - No authentication or authorization on any API endpoint (Critical)

**Evidence:** **backend/app.py** defines about 35 routes. None of them checks a session, a token or a user. The only access control in the product is in the browser: **frontend/src/router/index.js:45-52** checks for a **user** key in **localStorage**, and **frontend/src/App.vue:108** reads it back. **backend/app.py:324** carries the comment "In production, verify admin status from session/token", which was never implemented.

**Why it matters:** anyone who can reach port 5000 can call every endpoint without logging in, including **/api/query** (arbitrary SPARQL against the research data), **/api/data**, **/api/connections**, **/api/admin/users** and **/api/run-notebook**. Deleting the **user** key from browser storage is not even necessary; a single HTTP request is enough. The login screen provides no protection at all.

**Fix:** add real server-side sessions (Flask-Login or signed tokens), a decorator on every route, and role checks on the **/api/admin/** routes. Treat the frontend guard as cosmetic only.

**Verified:** by reading the full route list and searching for session, token and decorator patterns. Not confirmed against a running server, because that requires authorized testing.

### C2 - A default administrator account with the password "admin" is created automatically (Critical)

**Evidence:** **backend/models.py:160-162**

    if not self.storage_path.exists():
        admin = User('admin', User.hash_password('admin'), is_admin=True)

**Why it matters:** every fresh installation, including the VM deployment, starts with **admin / admin** and full administrator rights. Nothing forces a password change and nothing warns the operator. The documentation never mentions this account.

**Fix:** remove the auto-created account. Require an explicit first-run setup step that creates the first administrator with a chosen password, or generate a random password and print it once to the container log.

**Verified:** by reading the code. Worth confirming on the running VM (see the runtime checklist).

### H4 - Weak password hashing and no brute-force protection (High)

**Evidence:** **backend/models.py:56-62** uses a single unsalted SHA-256 pass:

    return hashlib.sha256(password.encode()).hexdigest()

**backend/app.py:253** implements **/api/login** with no rate limiting, no lockout and no logging of failures. **backend/config.py:152** sets a minimum password length of 6 and leaves strong-password enforcement off by default.

**Why it matters:** unsalted SHA-256 is fast and unsalted, so a stolen **users.json** can be cracked with rainbow tables or at billions of guesses per second. Identical passwords produce identical hashes, which reveals password reuse across accounts.

**Fix:** switch to Argon2id (or bcrypt, or PBKDF2 with a high iteration count) with a per-user salt, migrate existing hashes on next login, and add rate limiting to the login route.

**Verified:** by reading the code.

---

## B. Secrets and credentials

### C3 - Database credentials are stored in clear text and handed out by an unauthenticated endpoint (Critical)

**Evidence:** **backend/models.py:85** stores the connection password as given, **backend/models.py:110** includes it in **to_dict()**, **backend/models.py:284-289** returns connections unchanged, and **backend/app.py:451** exposes them through **GET /api/connections** with no masking and no authentication. The values are persisted in clear text in **backend/data/connections.json** (Docker volume **backend_data_volume**).

**Why it matters:** the AllegroGraph account used by Thinx is an administrator account. One unauthenticated GET request returns the host, port, repository, username and password, which is enough to connect to the triple store directly and read, alter or delete the entire research dataset. **README.md:196** states the opposite: "Passwords are encrypted and never displayed after entry."

**Fix:** encrypt credentials at rest with a key held outside the data volume, never return the password field from the API, and put the endpoint behind authentication. Prefer a service account with least privilege over an administrator account.

**Verified:** by reading the code path end to end.

### H1 - Live credentials are committed to a public repository (High)

**Evidence:**

- **push_to_allegrograph.py:146** - **password = os.getenv("AGRAPH_PASSWORD", "TUHB-KGDFCpUiTbL")**, a generated password used as the fallback default.
- **federated_query.py:20-22** - three repositories named after team members with **admin / admin123**.
- **list_repos.py:9** - a hosted AllegroGraph Cloud endpoint, **ag1s5fv23e82hv78.allegrograph.cloud**.
- **docker-compose.yml:47** - the database password **admin1233** in the file itself.

**Why it matters:** the repository is public, so these values are readable by anyone and are preserved in the git history even after a later edit. If any of them is still valid on a reachable server, this is a direct route into a database holding interview data about trafficking victims.

**Fix:** rotate every credential that has ever been committed, move all of them to environment variables with no secret defaults, purge them from the git history (git filter-repo or BFG, followed by a force push and a rotation of anything that cannot be purged), and add a secret scanner such as gitleaks to the workflow.

**Verified:** by reading the files in a clean clone. Whether the credentials are still live is unknown and must be checked by the repository owner.

---

## C. Code execution and network exposure

### H2 - The backend runs in Flask debug mode and is exposed on all interfaces (High)

**Evidence:** **backend/app.py:2039** ends with **app.run(host='0.0.0.0', port=5000, debug=True)**, and **docker-compose.yml:136-138** sets **FLASK_ENV=development** and **FLASK_DEBUG=1**. The container publishes port 5000. The pinned **Werkzeug 3.0.1** carries advisory **GHSA-2g68-c3qc-8985** (High), remote code execution through the debugger.

**Why it matters:** the Werkzeug debugger turns any unhandled exception into an interactive page, and its console can lead to code execution on the server. Stack traces also disclose source code and environment details. This is a development configuration shipped as the deployment configuration.

**Fix:** run the backend with a production WSGI server (gunicorn or waitress), force **debug=False**, and keep **FLASK_ENV=production**.

**Verified:** by reading the code and the compose file, and by the OSV.dev lookup for Werkzeug 3.0.1.

### H3 - Unauthenticated notebook execution with no path confinement (High)

**Evidence:** **backend/app.py:1166-1205**. The endpoint accepts any **notebook** value that ends in **.ipynb**, joins it onto **/workspace** with no normalization or containment check, and runs **jupyter nbconvert --execute --inplace** on it as root.

**Why it matters:** notebook code is arbitrary Python. Because the check is only on the file suffix, a relative path such as **../** escapes the intended directory, and **/workspace** is a read-write bind mount of the entire project directory on the host (**docker-compose.yml**, **.:/workspace**). Combined with C1, any unauthenticated caller can trigger execution of notebook code inside the container.

**Fix:** require authentication, restrict the parameter to a fixed allowlist of the two pipeline notebooks, resolve the path and verify it stays inside the intended directory, and run the pipeline as a non-root user. Converting the notebooks into plain Python modules would remove this endpoint altogether (see L6).

**Verified:** by reading the endpoint and the compose mounts.

### H6 - No transport encryption, and certificate validation is disabled for the external FAIR Data Point (High)

**Evidence:** the compose stack serves plain HTTP on 8080, 5000, 10035 and 11434; there is no TLS termination anywhere in the repository. **backend/utils/fair_data_point.py:16** defaults to **verify_ssl=False** against **https://fairdp.colo.ba.be**, and **backend/app.py:1909, 1963, 2013** pass **verify_ssl=False** explicitly.

**Why it matters:** login credentials, database credentials and query results, which include special-category personal data, travel unencrypted. Disabling certificate validation makes the FAIR Data Point calls trivially interceptable and modifiable in transit. The docstrings in the same file claim that no external calls are made, which is not true of this module.

**Fix:** put the stack behind a reverse proxy with TLS (Caddy, nginx plus Let's Encrypt, or the institution's ingress), set secure cookies, and fix the certificate chain of the FAIR Data Point instead of disabling validation.

**Verified:** by reading the code and the compose file, and first hand during deployment (the stack was reachable over plain HTTP only).

### M3 - Containers run as root, the project directory is bind-mounted read-write, and published ports bypass the host firewall (Medium)

**Evidence:** neither **backend/Dockerfile** nor **frontend/Dockerfile** contains a **USER** directive. **docker-compose.yml** mounts **./backend:/app** and **.:/workspace** read-write into the backend container. The original port mappings published 10035 and 11434 on all interfaces; Docker inserts its own iptables rules, so a host firewall such as ufw does not block published ports.

**Why it matters:** a flaw in the application becomes root inside the container with write access to the project directory on the host, and the database and the AI service are reachable from the network unless the operator intervenes. In this deployment that was mitigated by binding every port to 127.0.0.1 and using an SSH tunnel, but that mitigation is not in the repository.

**Fix:** add a non-root **USER** to both images, mount the workspace read-only where possible and write outputs to a dedicated volume, bind published ports to 127.0.0.1 in the committed compose file, and document the reverse proxy as the only public entry point.

**Verified:** by reading the Dockerfiles and the compose file, and first hand during deployment.

---

## D. Supply chain

### H5 - Pinned dependencies carry 89 known advisories, 22 of them high or critical (High)

**Evidence:** queried against the OSV.dev database on 2026-09-19 for the exact pinned versions in **backend/requirements.txt** and **frontend/package.json**:

| Package | Pinned | Advisories | High or critical |
|---|---|---|---|
| axios | 1.6.2 | 29 | 13 |
| vite | 5.0.0 | 18 | 3 |
| Werkzeug | 3.0.1 | 12 | 1 |
| urllib3 | 1.26.18 | 12 | 4 |
| flask-cors | 4.0.0 | 10 | 1 |
| requests | 2.31.0 | 6 | 0 |
| nbconvert | 7.12.0 | 6 | 1 |
| Flask | 3.0.0 | 2 | 0 |
| python-dotenv | 1.0.0 | 2 | 0 |

Named examples: **GHSA-2g68-c3qc-8985** (Werkzeug debugger, remote code execution), **GHSA-3g43-6gmg-66jw** (axios, credential theft through prototype pollution), **GHSA-hxwh-jpp2-84pm** (flask-cors, private-network CORS header enabled by default), **GHSA-qccp-gfcp-xxvc** (urllib3, sensitive headers forwarded across origins).

There is also no **package-lock.json** in the repository, so frontend builds are not reproducible, and **docker-compose.yml:79** pins **ollama/ollama:latest**, which changes under the deployment without notice.

**Why it matters:** these are the versions that actually run. The project has no dependency scanning, no update process and no lockfile for the frontend.

**Fix:** upgrade all pinned versions, commit **package-lock.json**, pin the Ollama image to a digest or a version tag, and add automated scanning (Dependabot or Renovate, plus pip-audit and npm audit in CI).

**Verified:** by an automated OSV.dev API query on 2026-09-19. The raw result is reproducible with the script in this folder; re-run it before quoting the numbers, because they grow over time.

---

## E. Privacy and GDPR

### M1 - Special-category personal data is processed without access control, audit trail or retention rules (Medium)

**Evidence:** the data model in **hds_cdm.ttl** and the mock dataset columns (read locally from **Mock data/DT01.xlsx**) include: year of birth, gender, nationality, sexual violence experienced and witnessed with type, human rights abuses, deaths witnessed, trafficker identity and nationality, borders crossed and payments. That is GDPR Article 9 special-category data (sex life, health, ethnic origin) combined with Article 10 data (criminal offences), about people in a highly vulnerable position.

Against that, the platform has: no working access control (C1, C2), no audit log of who ran which query or exported which dataset (the logger in **backend/logger.py** records application events, not data access), no retention or erasure function, no consent or purpose registration, and no pseudonymization step in the pipeline beyond what the source file already contains.

**Why it matters:** for this data category the GDPR expects a data protection impact assessment, documented access control, logging of access, and retention limits. Re-identification risk is real even without names: a combination of year of birth, nationality, border and date narrows records to very few individuals.

**Fix:** treat this as a FieldLab deliverable. Write a short DPIA, add per-user access control and an access log, define retention and deletion, and document the legal basis and the controller. Keep production data out of the repository and out of developer machines.

**Verified:** column names read locally from the mock file; the absence of controls verified by code review.

### M2 - The documentation claims protections that the code does not implement (Medium)

**Evidence:** **README.md:66** ("GDPR compliant and secure"), **README.md:196** ("Passwords are encrypted and never displayed after entry"), **README.md:290**, **README.md:764-766** ("Anonymized - No personally identifiable information", "GDPR compliant"), **USER_GUIDE.md:333** ("Platform protects data with encryption and access controls"), **FAQ.md:634** ("Hashed passwords (encrypted, not plaintext)"). Findings C1, C3 and H4 contradict each of these.

**Why it matters:** a researcher or FieldLab partner reading the documentation will believe the data is protected and will act accordingly, for example by uploading real interview data. Overclaiming compliance is itself a risk, and in an audit it is worse than a documented gap.

**Fix:** rewrite the security and privacy sections to describe the current state honestly, and add a clear warning that the platform is a research prototype that must not hold real data until the access-control findings are closed.

**Verified:** by reading the documentation against the code.

### M4 - Real data can end up in the git repository (Medium)

**Evidence:** the pipeline writes **data.xlsx**, **victims.json** and **cleaned_data.json** into **/workspace**, which is the project directory itself (**docker-compose.yml**, **.:/workspace**). **.gitignore** covers those three names and **\*.xlsx**, but not **uploads/\*.json**, which is where **/api/upload** stores uploaded JSON (**backend/app.py:1060-1063**). The committed **processing.ipynb** also stores 29 output cells, including frequency tables derived from the source dataset (for example nationality counts in cell 16).

**Why it matters:** an accidental **git add** publishes interview data to a public repository. Notebook outputs are an easy blind spot, because they are invisible in a normal diff review.

**Fix:** move the pipeline's working directory to a volume outside the repository, extend **.gitignore** to cover **uploads/**, strip notebook outputs on commit (nbstripout as a pre-commit hook), and add a pre-commit secret and data scan.

**Verified:** by reading the compose mounts, the upload endpoint, **.gitignore**, and by parsing the committed notebook locally.

### M7 - No encryption at rest and unencrypted backups (Medium)

**Evidence:** the AllegroGraph volume, the uploads and **connections.json** are stored unencrypted. The backup procedure in **ADMIN_GUIDE.md** produces plain tar archives with no encryption and no stated storage location or retention.

**Fix:** use an encrypted filesystem or volume for the data, encrypt backups (age or gpg), store them separately from the host, and document retention.

**Verified:** by reading the compose file and the admin guide.

---

## F. Application correctness and robustness

### M5 - Every upload overwrites one shared file, and connections are global (Medium)

**Evidence:** **backend/app.py:1042-1048** saves every uploaded spreadsheet as the fixed name **data.xlsx** in **/workspace**. **backend/models.py:284-289** filters connections by **user_id**, but nothing in the API ever sets a **user_id**, so all connections belong to everyone.

**Why it matters:** two researchers working at the same time silently destroy each other's data, and every user sees and can activate every other user's database connection. This also makes any future audit trail meaningless.

**Fix:** store uploads per user and per session under a generated identifier, record the owner on every connection, and scope reads to the owner.

**Verified:** by reading the code.

### M6 - Internal error messages are returned to the client (Medium)

**Evidence:** the pattern **return jsonify({'success': False, 'error': str(e)}), 500** appears throughout **backend/app.py** (for example lines 306, 596, 785, 876, 1084, 1356). **backend/app.py:1179-1196** additionally returns filesystem paths in its error payloads.

**Why it matters:** raw exception text leaks paths, library versions, SPARQL fragments and sometimes data values to whoever made the request, which helps an attacker and can leak personal data into browser logs.

**Fix:** return a generic message with a correlation identifier, and log the detail server-side only.

**Verified:** by reading the code.

### M8 - Age is silently lost for every victim when the interview date is stored as text (Medium). Closed.

**Evidence:** the first code cell of **processing.ipynb** keeps only the 17 original interview
columns, so a spreadsheet's own **age** column is discarded and age is recomputed from **Year of
birth** and **Date of the interview**. **calculate_age** (cell 20) recognised only a full timestamp
(**%Y-%m-%d %H:%M:%S**, what pandas produces from a real Excel date), a bare four-digit year, and
**25 April 2023**. All three mock datasets store the date as text, for example **2023-04-25**, so
all 100 rows of DT01 became **"not specified"**. **push_to_allegrograph.py:48-58** then fails to
turn that into an **xsd:integer** and **safe_add** drops the triple without a warning. No victim
received **hds:age**, and the Age column of every query and of the data viewer was empty.

**Why it matters:** a research field disappears without any error, and anything built on it is
wrong rather than visibly broken. **federated_query.py** averages **hds:age** across partners, so
one partner's missing ages silently distort the combined result.

**Fix applied:** one extra branch in **calculate_age** for text dates of the form **YYYY-MM-DD**.
The existing branches are unchanged. Every input that produced an age before takes the same branch
as before; only inputs that used to fall through to **"not specified"** now yield an age.

**Safety of the fix, pipeline:**

- The interview date never leaves the notebook. Cell 21 drops both date columns, so no JSON file,
  triple or query can read part of a date string.
- Every reader of age accepts an integer: **json_creator.ipynb** (its over-100 check), the push
  script (**xsd:integer**), **/api/data** and the data viewer, and **AVG(?age)** in
  **federated_query.py**.
- Both notebooks and the RDF generation were run on DT01 before and after the change. The only
  difference in **victims.json**, **cleaned_data.json** and the generated graph is 100 **hds:age**
  triples, typed **xsd:integer**, ages 18 to 54. The other differences seen between runs appear
  between two runs of the unchanged code as well (see below).

**Safety of the fix, FAIR feature:**

- The FAIR Data Point client (**backend/utils/fair_data_point.py** and the **/api/fair/** routes)
  only reads catalog and dataset metadata from the EEPA Data Point. No interview record is sent or
  published.
- Age is now written the way the ontology defines it: **hds:age** has range **xsd:integer** and is
  declared equivalent to **schema:age** (**hds_cdm.ttl:233-236**), so federated partners can combine it.
- A date such as **2023-04-25** is ISO 8601, the lexical form of **xsd:date**, which is the range of
  **hds:date** should interview dates ever be published.
- Interoperable does not mean open: age is flagged as sensitive in the backend's ontology endpoint,
  and the rule of no real interview data until H1, H6 and M1 are addressed still applies.

**Found along the way, not caused by the fix:**

- **json_creator.ipynb** builds **borders_crossed** from a Python set, so its order changes between
  runs (40 of 100 records in two identical runs). Extortion amounts are matched to borders by
  position, so with several payments per victim an amount can be attached to the wrong border.
- Every push re-parses **hds_cdm.ttl**, whose blank nodes get new identifiers each time, so the
  repository gains another copy of those ontology triples with every push.
- The computed age (interview year minus birth year) is one year below DT01's own **age** column in
  59 of 100 rows, because the birthday is unknown. The method is reasonable; the mock data generator
  simply counted differently.

**Verified:** by running both notebooks and the RDF generation on DT01 before and after the change,
and by comparing the outputs field by field.

---

## G. Engineering quality and maintainability

### L1 - Documentation does not match the code, which breaks first installation (Low)

**Evidence, all encountered first hand while deploying:** **docker-compose.yml:47** sets the database password to **admin1233** while **backend/config.py:61** and the documentation use **admin123**; the web UI is published on **8080** (**docker-compose.yml:201**) while **README.md** and **check-setup.sh** say port 80; **start.sh:36** runs **docker-compose up --build** although every service is behind a profile, so it starts nothing; **check-setup.sh:61** looks for the retired **docker-compose** binary rather than the **docker compose** plugin.

**Fix:** make one documented path work end to end, and test it on a clean machine. This is the cheapest credibility win available to the project.

**Verified:** first hand, during the deployment on the VM on 2026-09-18.

### L2 - Two competing configuration systems, one of which is dead code (Low)

**Evidence:** **backend/config.py** defines about 40 settings, including **CORS_ORIGINS**, **SECRET_KEY**, **OLLAMA_*** and **SESSION_***. **backend/app.py** never imports it. CORS is instead hardcoded at **backend/app.py:28-33** to **http://localhost** and **http://localhost:8080**. **docker-compose.yml** passes only five variables to the containers, so most of **.env.example** has no effect at all.

**Why it matters:** operators set variables that do nothing and believe they have configured the system. Accessing the UI by server IP fails with an unexplained CORS error, which is what happens to anyone deploying on a remote server.

**Fix:** make **app.py** import **config.py**, drive CORS from configuration, pass the variables through the compose file, and trim **.env.example** to what is actually read.

**Verified:** by reading both files and the compose file.

### L3 - The administrator guide documents a different project (Low)

**Evidence:** **ADMIN_GUIDE.md** instructs the reader to clone **https://github.com/Justin2280/DataScienceInPractice.git**, references **scripts/create_user.py** (absent), **UserManager.reset_password** (absent from **backend/models.py**), the container name **thinx_backend** (actual name **flask_api**) and **AllegroGraphClient.upload_rdf** (absent from **backend/utils/allegrograph.py**).

**Fix:** regenerate the guide from the code that exists, and add a documentation check to the review checklist.

**Verified:** by comparing the guide with the code.

### L4 - No continuous integration, no test suite, no licence (Low)

**Evidence:** no **.github/** directory, no CI configuration, and only two ad-hoc scripts (**backend/test_ai_mapper.py**, **backend/test_fair_data_point.py**) that are not a test suite. No **LICENSE** file, which blocks reuse and publication and sits awkwardly with the FAIR and open-science goals of VODAN.

**Fix:** add a minimal CI pipeline (lint, tests, pip-audit, npm audit, gitleaks), write tests for the data pipeline and the API, and agree a licence with the FieldLab owner.

**Verified:** by listing the repository.

### L5 - Development servers are used as the deployment target (Low)

**Evidence:** the frontend container runs **npm run dev** (**frontend/Dockerfile**, development stage), even though the same Dockerfile contains a production stage with nginx that the compose file never selects. The backend runs the Flask development server. The Vite HMR websocket is configured for port 80 (**frontend/vite.config.js:15-17**) while the service is published on 8080, so hot reload fails in the browser console.

**Fix:** use the existing **production** target for the frontend, gunicorn for the backend, and keep the development stack in a separate compose override file.

**Verified:** by reading the Dockerfiles, the compose file and the Vite configuration, and first hand in the browser console.

### L7 - The database container healthcheck can never pass (Low). Closed.

**Evidence:** **docker-compose.yml** defines the AllegroGraph healthcheck as a **curl** call, but
that image has no curl. On the deployed machine the container had failed its healthcheck 854 times
in a row and had been reporting **unhealthy** for as long as it had been running:

    "Output": "OCI runtime exec failed: exec: \"curl\": executable file not found in $PATH"

**Why it matters:** an always-unhealthy container makes the health signal worthless. Nobody can tell
a real database failure from the permanent false alarm, and any orchestration or monitoring built on
it is misleading.

**Fix applied:** the check is now a TCP probe run through **bash**, which that image does have
(its **/bin/sh** is dash and has no **/dev/tcp**). The container now reports healthy.

**Verified:** by reading the container health log on the deployed machine, and afterwards by the
container reporting healthy.

### L6 - The pipeline executes notebooks in place, so runs are not reproducible (Low)

**Evidence:** **backend/app.py:1201-1205** runs **jupyter nbconvert --to notebook --execute --inplace**, which rewrites the notebook in the repository on every run and mixes code, data-derived output and version control.

**Fix:** extract the pipeline into plain Python modules with unit tests and call those from the API; keep notebooks for exploration only.

**Verified:** by reading the endpoint.

---

## Priorities

**Before any real interview data is loaded into any Thinx instance:** C1, C2, C3, H1, H2, H3.

**Sprint 1 (about one week, low effort, high value):** remove the default admin account (C2), stop returning connection passwords (C3), switch off debug mode (H2), restrict the notebook endpoint to an allowlist (H3), rotate and purge committed credentials (H1), bind ports to localhost and add a non-root user (M3), correct the misleading documentation claims (M2, L1).

**Sprint 2:** server-side authentication and roles (C1), password hashing (H4), TLS through a reverse proxy (H6), dependency upgrades with a lockfile and CI scanning (H5).

**Sprint 3, FieldLab deliverables:** DPIA, access logging, retention and erasure (M1), per-user data isolation (M5), pipeline as tested modules (L6), configuration cleanup (L2), documentation regeneration (L3), CI, tests and licence (L4).

---

## What is still outstanding

1. **Rotate what the git history exposed.** Four credentials were committed at some point; removing
   them from the working tree does not remove them from the history. They must be rotated wherever
   they were used, and the history rewritten or the repository replaced. This needs the repository
   owner. The system owner has confirmed that no real interview data has ever been loaded into this
   deployment, which limits the blast radius but does not change the need to rotate.
2. **TLS in front of the stack**, and a fix for the FAIR Data Point certificate so that validation
   can be switched back on.
3. **Governance documents**: DPIA, processing agreement, controller, retention rules. These do not
   exist yet as far as the team knows, and writing them is a FieldLab deliverable.
4. **The old admin account on the deployed instance**, as noted above.
5. **Whether to propose the fixes upstream.** They currently sit on the fork branch **Ali** with
   **SECURITY_FIXES.md**; the FieldLab decides if and when they go to VODAN-Development.

## Changes made to the test machine during this work

Recorded here so nothing is a surprise later:

- On 2026-09-21 the repository in **/opt/thinx** was moved from branch **Ali** to **test_Ali**,
  identical to GitHub. Its one unpushed commit on **Ali** (port bindings, a password default and
  notebook run metadata) is fully superseded by what is on GitHub and was left on that branch
  untouched. That checkout would need a **SECRET_KEY** in its **.env** before it could be started.
- The fixed branch runs from **/opt/thinx-ali**; the original deployment in **/opt/thinx** was
  stopped, not deleted, and can be started again with **cd /opt/thinx && docker compose --profile
  full up -d**. Both use the same Docker volumes, so the data is the same either way.
- The machine could not resolve any hostname, because this network blocks port 53, so
  **/etc/systemd/resolved.conf** was changed to use DNS over TLS on port 853 and the Docker daemon
  was pointed at the host resolver. Without that, no image could be pulled and no dependency
  installed. The originals are kept as **/etc/systemd/resolved.conf.bak-thinx** and
  **/etc/docker/daemon.json.bak-thinx**.
- A test account named **sectest** was created to prove the role check and was deleted afterwards.
- Logging in as **admin** once during testing upgraded that account's stored password hash to the
  new format. The password itself is unchanged.
