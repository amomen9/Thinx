# Encryption in transit and internal services (D-S6)

Fixes issues S3 (no encryption in transit) and S8 (services published on the host).

## What changed

- **Caddy** (`Caddyfile`, service `caddy` in `docker-compose.yml`) is now the only
  service reachable from outside Docker. It serves Thinx over HTTPS, redirects
  HTTP to HTTPS, forwards `/api/*` to the backend and everything else to the
  frontend, and sets security headers (HSTS, X-Frame-Options, nosniff).
  This follows the approach used in FAIR Data Sphere.
- **Backend, AllegroGraph, Ollama and the frontend dev server** no longer publish
  ports on the host; they are only reachable on the internal Docker network.
- **The frontend** calls the API on its own address (`/api`) instead of
  `http://localhost:5000`.
- **FAIR Data Point calls** verify TLS certificates again (`FDP_VERIFY_SSL`, default
  `true`); before, `verify_ssl=False` accepted any certificate.

## Use

```
docker compose --profile full up --build
```

Open **https://localhost**. Caddy issues a certificate from its own local CA, so
the browser warns the first time. To trust it on this computer:

```
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
# macOS:
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt
```

On a server with a real domain, set in `.env`: `THINX_DOMAIN=your.domain`,
`THINX_TLS=your e-mail` (Caddy then gets a Let's Encrypt certificate) and
`THINX_BIND=0.0.0.0`.

To open the AllegroGraph web interface for administration, uncomment its
`127.0.0.1:10035` port line in `docker-compose.yml` temporarily.

## Verification

With Thinx running: `./scripts/check_tls.sh`. It checks HTTPS for the API and the
frontend, the HTTP to HTTPS redirect, the security headers, the certificate, and
that ports 5000, 10035, 11434 and 8080 are closed on the host.

Traffic between the containers on the internal Docker network is not encrypted;
it never leaves the machine. Encrypting it (e.g. TLS to AllegroGraph) is future work.
