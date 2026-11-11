# Encryption of RDF data at rest (D-S7)

Decision for open security decision 2 of the Technical Plan: **disk-level
encryption** of the storage that holds the AllegroGraph data, not field-level
encryption inside the RDF.

## Problem (issue S1)

AllegroGraph stores the triples in the Docker volume `agraph_data_volume` in
plaintext. Anyone who gets hold of the disk, a copy of the volume or a stolen
laptop can read the victim data without logging in to Thinx or AllegroGraph.

## Options considered

| | Disk-level encryption | Field-level encryption |
|---|---|---|
| What is encrypted | The whole disk or volume the Docker data lives on | Selected literals (e.g. names, nationality) before they are written to RDF |
| Protects against | Stolen or lost device, copied disk image, discarded hardware | Same, plus database administrators reading those fields |
| Effect on Thinx | None: AllegroGraph, SPARQL and the ETL keep working unchanged | Encrypted values cannot be filtered, joined or matched in SPARQL; the ETL, the queries and federated querying in the HDS would all have to change |
| Key management | One key per machine, handled by the operating system | Application keys, rotation and access rules per field |
| Effort | Configuration and documentation | Large change to the pipeline and every query |

## Decision

We use disk-level encryption. Thinx is built around SPARQL queries over the
RDF and federated querying in the Humanitarian Data Space; field-level
encryption would break exactly those features, while the main risk in S1 is
access to the raw storage. Field-level encryption of the most sensitive
attributes stays a recommendation for future work (Technical Plan, Section 6.3).

What disk-level encryption does **not** cover: someone with access to the
running system (logged-in user, compromised backend) still sees decrypted data.
That is handled by access control (D-A1) and by keeping the services off the
network (D-S1, D-S6). Backups need their own encryption (D-S8).

## How to set it up

The data is encrypted when the disk that holds Docker's data is encrypted:

- **macOS (Docker Desktop):** turn on FileVault (System Settings → Privacy &
  Security → FileVault). Docker Desktop keeps its volumes in a disk image in the
  user's Library, so FileVault covers them.
- **Windows (Docker Desktop):** turn on BitLocker for the system drive.
- **Linux server:** put Docker's data directory (`/var/lib/docker`, or the
  `data-root` in `/etc/docker/daemon.json`) on a LUKS-encrypted partition,
  ideally set up during installation. The same applies to the encrypted
  storage for raw data (open decision 1).

Then run `./scripts/check_encryption_at_rest.sh` to confirm.

## Verification

1. `./scripts/check_encryption_at_rest.sh` reports that Docker's data is on an
   encrypted disk (FileVault on, or a `crypt` device under the Docker data root).
2. With the machine shut down (or the LUKS volume locked), the volume content is
   not readable: on Linux, `strings` on the raw partition shows no triples from
   the mock data, e.g. no `hds:` or victim nationality literals.
