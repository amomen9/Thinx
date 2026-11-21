# Sensitive data in the graph (D-S9)

`backend/data_protection.py` gives the ETL and the backend three tools for rule R12 of the
on-top mapping (sensitive classes) and for stable identifiers (Doruk's Q8).

## For the ETL (transform/load)

```python
from data_protection import encrypt_value, stable_id

actor_iri = BASE + 'actor/' + stable_id('actor', alias_or_id)        # not :actor/{alias}
place_iri = BASE + 'place/' + stable_id('place', interview_place)    # only for the interview location
g.add((actor, FOAF.name,   Literal(encrypt_value(name))))
g.add((actor, THINX.alias, Literal(encrypt_value(alias))))
g.add((actor, THINX.traffickerRaw, Literal(encrypt_value(raw_cell))))  # raw twins too
```

* Encrypt **after** the datatype check (R12) and before the RDF is written or uploaded.
* Encrypted: trafficker name / alias / ID text, location of the interview, and their raw twins.
* `stable_id` normalises case, accents and spacing, so the same alias in one dataset version
  gives one actor node (R5). Without `ID_HMAC_KEY` nobody can recompute or guess the ID.
* Places of events and countries stay readable (`:place/kassala`); only the interview location
  can point to a person.

## For SHACL (D-T3)

```turtle
sh:property [ sh:path foaf:name ;   sh:pattern "^enc:v1:gAAAA" ] ;
sh:property [ sh:path thinx:alias ; sh:pattern "^enc:v1:gAAAA" ] ;
```

A plain-text name then fails validation before the upload.

## In the backend

`/api/query` and `/api/data` pass results through `protect_results(results, user)`:

| User | Encrypted values | Coercion types (special category) |
|---|---|---|
| admin, or `can_view_sensitive: true` | decrypted | shown |
| everyone else | `<restricted>` | `<restricted>` |

An admin sets `can_view_sensitive` with `PUT /api/admin/users/<id>`.

**Limitation.** `/api/query` accepts free SPARQL, so filtering the results is a safeguard, not
full access control: a user could still test for a restricted concept inside a `FILTER`. Full
separation needs a separate AllegroGraph repository or account for the restricted data.
Encrypted values stay safe in any case, because the key never leaves the backend.

## Keys (.env)

| Variable | What | If lost |
|---|---|---|
| `DATA_ENCRYPTION_KEY` | Fernet key for sensitive literals; not the connection key | encrypted values cannot be read |
| `ID_HMAC_KEY` | ≥ 32 characters, for `stable_id` | IRIs change on the next upload |

Both belong in `.env` only, never in git, and are shared only with the people who run the
deployment.
