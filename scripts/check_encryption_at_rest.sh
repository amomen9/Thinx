#!/usr/bin/env bash
# Checks that the AllegroGraph data (Docker volume) is on an encrypted disk (D-S7).
# Usage: ./scripts/check_encryption_at_rest.sh
# Exit code 0 = encrypted, 1 = not encrypted, 2 = could not determine.

set -u
VOLUME="${AGRAPH_VOLUME:-agraph_data_volume}"

echo "Thinx encryption-at-rest check (D-S7)"
echo "--------------------------------------"

if command -v docker >/dev/null 2>&1 && docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  echo "AllegroGraph volume: $VOLUME (found)"
else
  echo "AllegroGraph volume: $VOLUME (not found; start Thinx once, or set AGRAPH_VOLUME)"
fi

case "$(uname -s)" in
  Darwin)
    status="$(fdesetup status 2>/dev/null || true)"
    echo "macOS FileVault: ${status:-unknown}"
    if echo "$status" | grep -q "FileVault is On"; then
      echo "RESULT: OK - Docker Desktop volumes are stored on the FileVault-encrypted disk."
      exit 0
    fi
    echo "RESULT: NOT ENCRYPTED - turn on FileVault (System Settings > Privacy & Security > FileVault)."
    exit 1
    ;;
  Linux)
    root="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null | tr -d '[:space:]')"
    root="${DOCKER_ROOT:-${root:-/var/lib/docker}}"
    # findmnt needs an existing path; fall back to the closest existing parent
    target="$root"
    while [ ! -e "$target" ] && [ "$target" != "/" ]; do target="$(dirname "$target")"; done
    src="$(findmnt -n -o SOURCE --target "$target" 2>/dev/null || true)"
    echo "Docker data root: $root"
    echo "Mounted from:     ${src:-unknown}"
    if [ -z "$src" ]; then
      echo "RESULT: UNKNOWN - could not find the device for $root."
      exit 2
    fi
    # Walk up the block-device tree (partition -> LVM -> dm-crypt) and look for a crypt layer.
    if lsblk -s -n -o TYPE "$src" 2>/dev/null | grep -q "crypt"; then
      echo "RESULT: OK - $root is on a dm-crypt/LUKS encrypted device."
      exit 0
    fi
    echo "RESULT: NOT ENCRYPTED - put $root on a LUKS-encrypted partition (see docs/SECURITY_ENCRYPTION_AT_REST.md)."
    exit 1
    ;;
  *)
    echo "On Windows, check BitLocker with: manage-bde -status C:   (in an administrator PowerShell)"
    echo "RESULT: UNKNOWN - automatic check only supports macOS and Linux."
    exit 2
    ;;
esac
