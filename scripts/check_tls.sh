#!/usr/bin/env bash
# Verifies D-S6 on a running Thinx: HTTPS works, HTTP redirects to HTTPS, security
# headers are set, and backend, AllegroGraph and Ollama are not reachable from the host.
# Usage: ./scripts/check_tls.sh            (after: docker compose --profile full up -d)
# Exit code 0 = all checks passed.

set -u
DOMAIN="${THINX_DOMAIN:-localhost}"
fails=0
ok()   { echo "  OK    $1"; }
fail() { echo "  FAIL  $1"; fails=$((fails + 1)); }

echo "Thinx TLS check (D-S6) for https://$DOMAIN"

# -k: Caddy's local CA may not be trusted by curl yet; the certificate itself is checked below
code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$DOMAIN/api/health")
[ "$code" = "200" ] && ok "API over HTTPS (https://$DOMAIN/api/health -> 200)" || fail "API over HTTPS returned $code"

code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$DOMAIN/")
[ "$code" = "200" ] && ok "frontend over HTTPS -> 200" || fail "frontend over HTTPS returned $code"

redirect=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "http://$DOMAIN/")
case "$redirect" in
  30[18]\ https://*) ok "HTTP redirects to HTTPS ($redirect)" ;;
  *) fail "HTTP does not redirect to HTTPS ($redirect)" ;;
esac

headers=$(curl -sk -D - -o /dev/null "https://$DOMAIN/")
echo "$headers" | grep -qi '^strict-transport-security' && ok "HSTS header set" || fail "HSTS header missing"
echo "$headers" | grep -qi '^x-frame-options: *DENY' && ok "X-Frame-Options: DENY" || fail "X-Frame-Options missing"

issuer=$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null \
         | openssl x509 -noout -issuer 2>/dev/null)
[ -n "$issuer" ] && ok "certificate served (${issuer#issuer=})" || fail "no certificate on port 443"

for port in 5000 10035 11434 8080; do
  if curl -s -m 3 -o /dev/null "http://127.0.0.1:$port/" 2>/dev/null; then
    fail "port $port is reachable from the host (should be internal only)"
  else
    ok "port $port is closed on the host"
  fi
done

echo
if [ "$fails" -eq 0 ]; then echo "RESULT: all checks passed"; exit 0; fi
echo "RESULT: $fails check(s) failed"; exit 1
