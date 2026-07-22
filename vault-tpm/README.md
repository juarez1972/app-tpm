# HashiCorp Vault with TPM-Validated Auto-Unseal

![app-tpm](https://img.shields.io/badge/project-app--tpm-blue)
![HashiCorp Vault](https://img.shields.io/badge/HashiCorp%20Vault-1.15%2B-black?logo=vault)
![Docker](https://img.shields.io/badge/docker-compose-blue?logo=docker)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)

> Component of the prototype described in:
> **"A Hybrid Zero Trust Architecture for Non-Interactive Authentication"**
> Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. — PPGIa/PUCPR, Brazil.

This module implements **Hardware Auto-Unseal for HashiCorp Vault** using a TPM 2.0 chip as the root of trust. The Vault process will not unseal until the host's TPM passes integrity validation — establishing a hardware chain of trust that eliminates manual unseal operations and prevents Vault from starting on a tampered or unauthorized machine.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Prerequisites](#4-prerequisites)
5. [Configuration](#5-configuration)
6. [Running the Stack](#6-running-the-stack)
7. [Component Details](#7-component-details)
8. [Validation & Testing](#8-validation--testing)
9. [Unversioned / Runtime Artifacts](#9-unversioned--runtime-artifacts)
10. [Notes](#10-notes)

---

## 1. Overview

`vault-tpm` addresses the **Secret Zero problem** in Infrastructure as Code: how to bootstrap secret management without storing an initial plaintext credential anywhere. The solution seals the Vault unseal keys inside a TPM 2.0 — a dedicated tamper-resistant chip — so the keys never touch disk in plaintext and can only be recovered on the same host TPM that sealed them.

**Key capabilities:**

- **Real Vault initialization** (`sys/init`, 5 shares / threshold 3) on first boot, run automatically only when Vault is not yet initialized
- **TPM-sealed unseal keys**: each Shamir share and the root token are sealed under a persistent TPM SRK (`tpm2_create` / `tpm2_unseal`) — deterministic and recoverable across reboots
- **Automatic auto-unseal** on every boot: keys are unsealed from the TPM and applied via the Vault REST API (`sys/unseal`) until the threshold is met
- **Exponential backoff + jitter** while waiting for Vault and when applying unseal keys, with graceful handling of "Vault not ready yet"
- **No plaintext secrets on disk** — only TPM-sealed `.enc` blobs (plus their `.pub`/`.priv`); no root token or unseal key is ever written in the clear
- No cloud dependency and no `vault` binary required in the container — the initializer talks to Vault purely over its REST API
- Continuous health endpoint (port 8080) served by `tpm-validator/tpm_validator.py` for external monitoring

**Port summary:**

| Service | Port | Protocol |
|---|---|---|
| HashiCorp Vault API | `8200` | HTTP (add TLS before production) |
| TPM Validator health endpoint | `8080` | HTTP |

---

## 2. Architecture

The stack consists of three containers orchestrated by Docker Compose. The dependency order is `vault` → `vault-initializer` → `tpm-validator`: Vault starts first (sealed), the initializer then performs init (if needed) and auto-unseal using TPM-sealed keys, and the validator runs continuously afterward to monitor health.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         vault-tpm stack                             │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  HOST MACHINE                                               │     │
│  │                                                             │     │
│  │  ┌──────────────┐  PCR measurement                         │     │
│  │  │   TPM 2.0    │──────────────────────────────────────┐  │     │
│  │  │  (hardware)  │                                       │  │     │
│  │  └──────────────┘                                       │  │     │
│  └─────────────────────────────────────────────────────────┼──┘     │
│                                                             │        │
│  ┌──────────────────────┐     ┌────────────────────────────▼──┐     │
│  │    tpm-validator      │     │         vault-init             │     │
│  │                       │     │                                │     │
│  │  tpm_validator.py     │     │  vault_initializer.py          │     │
│  │  health_check.py      │     │                                │     │
│  │                       │     │  1. Waits for Vault (backoff)  │     │
│  │  • Monitors TPM state │     │  2. If not initialized:        │     │
│  │  • Checks .enc files  │     │     sys/init + seal keys->TPM  │     │
│  │  • Checks Vault health│     │  3. Unseal keys from TPM ->    │     │
│  │  • Exposes port 8080  │     │     sys/unseal (retry/backoff) │     │
│  └───────────┬───────────┘     └───────────────┬───────────────┘     │
│              │  continuous                      │  reads/writes .enc  │
│              │  monitoring                      ▼                     │
│              │                    ┌─────────────────────────┐         │
│              │                    │     HashiCorp Vault      │         │
│              │                    │                          │         │
│              └───────────────────►│  Sealed at boot          │         │
│                                   │  Unsealed by initializer │         │
│                                   │  using TPM-sealed keys   │         │
│                                   │                          │         │
│                                   │  Port 8200               │         │
│                                   └──────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘

Boot sequence:
  Boot → Vault (sealed) → Initializer (init if needed + unseal from TPM) → Vault Operational → Validator monitors
```

**Startup sequence:**

1. Docker Compose starts `vault` first; it comes up **sealed** (and uninitialized on a fresh volume).
2. `vault-initializer` runs `vault_initializer.py`, which:
   - waits for Vault to answer `sys/health` using **exponential backoff + jitter**;
   - checks `sys/seal-status`; if Vault is **not initialized**, runs `sys/init` (5 shares / threshold 3), seals each unseal key and the root token into the TPM (`.enc` blobs in `tpm-data/`, not versioned);
   - if already initialized, **recovers the unseal keys from the TPM**;
   - applies the keys via `sys/unseal` (with retry/backoff) until Vault is unsealed.
   The container is one-shot (`restart: "no"`) and exits after Vault is operational.
3. `tpm-validator` runs continuously, periodically checking TPM state, presence of `.enc` files, and Vault health, exposing results on port 8080.

> **Note on the root token:** it is sealed into the TPM (`root_token.enc`) and never written to disk in plaintext. Recover it only on the host that owns the TPM. There is no `.txt` copy.

---

## 3. Directory Structure

```
vault-tpm/
├── docker-compose.yml              # Three-service orchestration (vault, vault-init, tpm-validator)
├── vault-config.hcl                # Vault server configuration (storage, listener, API address)
├── requirements.txt                # Top-level Python dependencies
├── README.md
│
├── scripts/
│   ├── setup_vault_policies.hcl   # Minimum-privilege Vault access policies (HCL)
│   ├── get_root_token.sh          # Recover a TPM-sealed token (root or app) to stdout only
│   └── revoke_root_token.sh       # Create least-privilege token, then revoke the root token
│
├── ci/
│   ├── test_seal_unseal.sh              # CI: init + seal/unseal + cross-boot recovery (swtpm)
│   └── test_tpm_integration_swtpm.sh    # CI: TPM basic + key operations (swtpm)
│
├── templates/
│   └── index.html                  # Web UI template served by tpm-validator
│
├── tpm-validator/
│   ├── Dockerfile                  # Container image (x86_64 / amd64)
│   ├── tpm_validator.py            # Main health-check service (port 8080)
│   ├── health_check.py             # TPM and Vault health-check helper
│   └── requirements.txt            # Python dependencies for this service
│
├── vault-init/
│   ├── Dockerfile                  # Container image (x86_64 / amd64)
│   ├── vault_initializer.py        # Vault init + TPM-sealed auto-unseal (retry/backoff)
│   └── requirements.txt            # Python dependencies for this service
│
├── setup_secret.sh                 # Smoke-test: writes/reads an example secret (token from TPM)
├── system_status.sh                # Displays overall stack health (TPM, Vault, containers)
├── test_tpm_integration.sh         # End-to-end TPM ↔ Vault test (physical TPM + full stack; not in CI)
└── validate_system.sh             # System validation script (token from TPM)
```

> The GitHub Actions workflow lives at repository root in [`.github/workflows/ci-seal-unseal.yml`](../.github/workflows/ci-seal-unseal.yml). A root-level [`.gitignore`](../.gitignore) excludes virtualenvs, caches, logs and runtime data (`tpm-data/`, `vault-data/`).

**Notes on unversioned / runtime artifacts** — see [Section 9](#9-unversioned--runtime-artifacts).

---

## 4. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | 24.0+ | Required |
| Docker Compose | v2.x | Required |
| Python | 3.10+ | For running scripts outside containers |
| TPM 2.0 | — | Physical chip (e.g., Infineon SLB9670) or software emulator (`swtpm`) |
| `tpm2-tools` | 5.x | Installed in the initializer/validator images and used via CLI; the host must expose `/dev/tpmrm0` |

**Operating system:** Linux (tested on Ubuntu 22.04 LTS).

#### Verify TPM availability on the host

```bash
# Check for TPM character devices
ls /dev/tpm*
# Expected: /dev/tpm0 and/or /dev/tpmrm0

# Verify TPM kernel modules
lsmod | grep tpm

# Quick functional test
sudo tpm2_getrandom 4
```

---

## 5. Configuration

### 5.1 Vault server — `vault-config.hcl`

`vault-config.hcl` configures the Vault server process itself: the storage backend (file-based by default for this prototype), the TCP listener address and port, and the public API address returned to clients.

```hcl
# vault-config.hcl (excerpt — adjust for production)
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true          # Enable TLS before deploying to production
}

api_addr = "http://0.0.0.0:8200"
```

> **Production note:** Set `tls_disable = false` and provide valid TLS certificates before any non-local deployment. The current configuration is intended for local development and testing only.

### 5.2 Access policies — `scripts/setup_vault_policies.hcl`

This HCL file defines minimum-privilege Vault policies for services that need to read or write secrets. Apply them after Vault is initialized:

```bash
vault policy write app-policy scripts/setup_vault_policies.hcl
```

Policies follow the principle of least privilege: each service receives only the capabilities (`read`, `list`, `create`, `update`, or `delete`) it strictly requires on the paths it accesses.

### 5.3 Initializer configuration (`vault-init/vault_initializer.py`)

The initializer runs Vault in **production mode** (no `-dev`, no default `root` token). Its behavior is controlled by environment variables (all optional; sensible defaults shown):

| Variable | Default | Description |
|---|---|---|
| `VAULT_ADDR` | `http://vault:8200` | Vault API address (internal network) |
| `TPM_DATA_DIR` | `/app/tpm-data` | Directory for the TPM-sealed `.enc` blobs |
| `TPM2TOOLS_TCTI` | `device:/dev/tpmrm0` | TPM TCTI (kernel resource manager) |
| `TPM_SRK_HANDLE` | `0x81010001` | Persistent SRK handle used to seal/unseal keys |
| `UNSEAL_KEY_SHARES` | `5` | Shamir shares generated at `sys/init` |
| `UNSEAL_KEY_THRESHOLD` | `3` | Shares required to unseal |
| `MAX_ATTEMPTS` | `30` | Attempts while waiting for Vault |
| `BASE_DELAY` / `MAX_DELAY` | `2` / `60` | Exponential backoff bounds (seconds) |

> If handle `0x81010001` is already used on your host TPM, set `TPM_SRK_HANDLE` to a free persistent handle.

### 5.4 Recovering the initial root token

The initial Vault **root token** is generated by `sys/init` and immediately **sealed into the TPM** (`root_token.enc` + `.pub`/`.priv`). It is **never written to disk in plaintext and never printed to the container logs** — the initializer only logs that it was sealed.

To obtain it, unseal it directly from the TPM with the helper [`scripts/get_root_token.sh`](scripts/get_root_token.sh). This runs `tpm2_load` + `tpm2_unseal` and prints the token to **stdout only** (nothing is written to disk):

```bash
cd vault-tpm

# Print the token (careful: it goes to your terminal / shell history):
./scripts/get_root_token.sh

# Preferred — load it into an env var without echoing it, then use the CLI:
export VAULT_ADDR="http://127.0.0.1:8201"          # host port mapped to the container
export VAULT_TOKEN="$(./scripts/get_root_token.sh --quiet)"
vault status
vault token lookup            # confirms you are authenticated (policies: root)

# Or log in interactively without exposing the token on the command line:
./scripts/get_root_token.sh --quiet | vault login -
```

For the **web UI**, open `http://<host>:8201/ui`, choose the **Token** method, and paste the value from `./scripts/get_root_token.sh --quiet`.

**Requirements / caveats:**

- Run it **on the host that owns the TPM** which sealed the token — the blobs are bound to that TPM's persistent SRK and cannot be unsealed elsewhere.
- In a VM/CI environment (emulated TPM), point it at the emulator: `export TPM2TOOLS_TCTI="swtpm:path=/path/to/swtpm-sock"` before running it.
- It reads the blobs from `TPM_DATA_DIR` (default `./tpm-data`). Override with `TPM_DATA_DIR=/path/to/tpm-data` if the volume lives elsewhere.
- **Security:** avoid piping the token into files or command arguments that land in logs/history. Prefer `--quiet` + a shell variable, as shown above. As a root token, rotate/revoke it after provisioning least-privilege tokens for day-to-day use.

### 5.5 Revoking the initial root token (least-privilege hardening)

The root token has unlimited power and should **not** be used for day-to-day operations. Once the stack is up, provision a least-privilege token and revoke the root. The helper [`scripts/revoke_root_token.sh`](scripts/revoke_root_token.sh) does this **safely and in order**:

1. Recovers the root token from the TPM (via `get_root_token.sh`).
2. Ensures the KV v2 engine is mounted at `secret/`.
3. Writes the app ACL policy `app-policy` from [`scripts/setup_vault_policies.hcl`](scripts/setup_vault_policies.hcl).
4. Creates a **child token** bound to that policy (renewable, TTL `APP_TOKEN_TTL`, default `768h`).
5. **Validates** the new token (lookup-self + write/read under `secret/data/tpm-verified/*`).
6. **Seals the new token into the TPM** as `app_token.enc` (no plaintext on disk).
7. Only then **revokes the root token** (`revoke-self`) and confirms it stops working (lookup-self → HTTP 403).

```bash
cd vault-tpm
export VAULT_ADDR="http://127.0.0.1:8201"

# Rehearse everything WITHOUT revoking the root (recommended first run):
./scripts/revoke_root_token.sh --dry-run

# Do it for real (creates + validates + seals app-token, then revokes root):
./scripts/revoke_root_token.sh
```

After revocation, use the least-privilege token for daily work. Recover it from the TPM the same way as the root, pointing at the `app_token` blob:

```bash
export VAULT_TOKEN="$(TOKEN_BASENAME=app_token ./scripts/get_root_token.sh --quiet)"
vault token lookup      # policies: [app-policy default]
```

**Important:**

- Revocation is **irreversible**. If you later need root privileges again, use Vault's official [`vault operator generate-root`](https://developer.hashicorp.com/vault/docs/commands/operator/generate-root) flow, which requires the unseal-key quorum (still sealed in the TPM). The initial root blob (`root_token.enc`) no longer authenticates once revoked.
- The script **aborts before revoking** if it cannot create/validate/seal the least-privilege token — so you never lose access without a working replacement.
- Tune the policy via `APP_POLICY_FILE` / `APP_POLICY_NAME` and the token lifetime via `APP_TOKEN_TTL`. In a VM/CI (emulated TPM), set `TPM2TOOLS_TCTI="swtpm:path=..."` as usual.

---

## 6. Running the Stack

### 6.1 Clone the repository

```bash
git clone https://github.com/juarez1972/app-tpm.git
cd app-tpm/vault-tpm
```

### 6.2 Bring up the full environment

```bash
docker-compose up -d
```

Docker Compose starts the three services in dependency order: `vault` → `vault-initializer` → `tpm-validator`. On a fresh volume the initializer runs `sys/init` once, seals the keys into the TPM, and unseals Vault; on later boots it recovers the keys from the TPM and unseals automatically.

### 6.3 Follow startup logs

```bash
docker-compose logs -f
```

### 6.4 Check overall system status

```bash
./system_status.sh
```

### 6.5 Write an example secret

After Vault is operational, populate an example secret using the provided helper:

```bash
./setup_secret.sh
```

`setup_secret.sh` authenticates to Vault **using the token recovered from the TPM** (no plaintext token is ever written to disk), ensures the KV v2 engine is mounted, then writes and reads back a sample key-value pair under `secret/data/tpm-verified/*` — useful for verifying that the unseal flow completed successfully and that write access is functioning. If the least-privilege `app_token` has already been sealed (see [5.5](#55-revoking-the-initial-root-token-least-privilege-hardening)), it is preferred automatically; otherwise the root token is used. You can also pass a token explicitly via `VAULT_TOKEN=... ./setup_secret.sh`.

### 6.6 Tear down the stack

```bash
docker-compose down
```

To also remove named volumes (including `tpm-data` and `vault-data`):

```bash
docker-compose down -v
```

---

## 7. Component Details

### 7.1 Component summary

| Container | Image source | Port | Role |
|---|---|---|---|
| `vault` | `hashicorp/vault` | `8200` (host `8201`) | Secret store; starts sealed, unsealed by the initializer |
| `vault-initializer` | `vault-init/Dockerfile` | — | One-shot: init (if needed), seals keys into TPM, auto-unseals via API |
| `tpm-validator` | `tpm-validator/Dockerfile` | `8080` | Continuous health monitor: TPM + `.enc` files + Vault |

### 7.2 `vault-init/vault_initializer.py`

Orchestrates the secure init + auto-unseal sequence over the Vault REST API (no `vault` binary needed):

1. **Verifies the TPM** is reachable (`tpm2_getrandom`); aborts if unavailable (no TPM = no key protection).
2. **Waits for Vault** to answer `sys/health`, using exponential backoff + jitter, tolerating connection-refused / not-ready states.
3. **Checks `sys/seal-status`.** If Vault is *not initialized*, calls `sys/init` (5 shares / threshold 3) and **seals** each unseal key and the root token into the TPM under the persistent SRK (`tpm2_create`), producing `.enc` marker files plus `.pub`/`.priv` blobs. If Vault *is* initialized, it **recovers** the unseal keys from the TPM (`tpm2_load` + `tpm2_unseal`).
4. **Unseals Vault** by posting the recovered keys to `sys/unseal` until the threshold is met, retrying transient errors with backoff.
5. Exits once Vault reports `sealed: false`. **No plaintext secrets are ever written** — there are no `.txt` copies.

> **Why sealing, not `tpm2_encryptdecrypt`:** sealing under a *persistent* SRK is deterministic and recoverable across reboots. An ephemeral primary context (created and discarded per run) could not decrypt the data later, which is why the earlier approach could not support real auto-unseal.

### 7.3 `tpm-validator/tpm_validator.py`

Runs as a long-lived service that:

- Periodically checks TPM accessibility (via `tpm2_getrandom` or equivalent).
- Verifies that the expected `.enc` files are present in the `tpm-data/` volume.
- Polls the Vault health endpoint (`GET /v1/sys/health`).
- Exposes all results on port **8080** via an HTTP health endpoint — the `templates/index.html` provides a simple web dashboard for this data.

### 7.4 `tpm-validator/health_check.py`

Helper module called by `tpm_validator.py`. Encapsulates individual health-check functions for the TPM subsystem and Vault API, keeping the main service file focused on HTTP serving and scheduling.

### 7.5 `scripts/setup_vault_policies.hcl`

HCL policy definitions for minimum-privilege Vault access. Referenced in the root README (Section 6.2) as part of the broader secret lifecycle. Apply after initialization using the Vault CLI (see [Section 5.2](#52-access-policies--scriptssetup_vault_policieshcl)).

### 7.6 `vault-config.hcl`

Vault server configuration file: defines the storage backend, TCP listener, and public API address. Mounted into the `vault` container at startup. See [Section 5.1](#51-vault-server--vault-confighcl) for details.

### 7.7 Shell scripts

| Script | Purpose |
|---|---|
| `scripts/get_root_token.sh` | Recovers a TPM-sealed token (root by default, or any via `TOKEN_BASENAME`) and prints it to **stdout only** — nothing written to disk or logs. See [5.4](#54-recovering-the-initial-root-token). |
| `scripts/revoke_root_token.sh` | Creates a least-privilege token (policy `app-policy`), validates it, seals it in the TPM (`app_token`), then revokes the root token. Supports `--dry-run`. See [5.5](#55-revoking-the-initial-root-token-least-privilege-hardening). |
| `setup_secret.sh` | Smoke-test: authenticates with the TPM-recovered token (prefers `app_token`, else root), then writes and reads back an example secret. No plaintext token on disk. |
| `validate_system.sh` | Full system validation; authenticates with the TPM-recovered token (no hardcoded token). |
| `system_status.sh` | Queries and prints the health of all three containers, the TPM device, and Vault. |
| `test_tpm_integration.sh` | End-to-end integration tests against the running stack — **requires a physical TPM (`/dev/tpmrm0`) and is not run in CI** (see [CI section](#tpm-integration-test-citest_tpm_integration_swtpmsh)). |
| `ci/test_seal_unseal.sh` | CI test (swtpm): init + seal/unseal + cross-boot recovery + root-token auth. See [CI section](#automated-ci-test-citest_seal_unsealsh). |
| `ci/test_tpm_integration_swtpm.sh` | CI test (swtpm): basic TPM ops + key ops, without docker-compose or a physical TPM. |

---

## 8. Validation & Testing

### 8.1 TPM health

```bash
# From the host
sudo tpm2_getrandom 4

# Via the tpm-validator health endpoint
curl http://localhost:8080/status
```

### 8.2 Vault health

```bash
curl http://localhost:8200/v1/sys/health
```

Expected response for a healthy, unsealed Vault:

```json
{
  "initialized": true,
  "sealed": false,
  "standby": false,
  "performance_standby": false,
  "replication_performance_mode": "disabled",
  "replication_dr_mode": "disabled",
  "server_time_utc": 1234567890,
  "version": "1.15.x"
}
```

### 8.3 Container logs

```bash
docker-compose logs --tail=20
docker-compose logs vault-init --tail=50
docker-compose logs tpm-validator --tail=20
```

### 8.4 Integration test suite

```bash
./test_tpm_integration.sh          # requires a physical TPM + the full stack up
```

The test suite covers real-time TPM validation, inter-container communication, Vault write/read, data persistence across restarts, automatic recovery, and continuous health checks. It needs a **physical TPM (`/dev/tpmrm0`)** and the running `docker-compose` stack, so it is **not** executed in CI.

For CI (and any VM without a physical TPM), the equivalent checks run against the **emulated TPM (swtpm)**:

```bash
./ci/test_seal_unseal.sh                 # init + seal/unseal + cross-boot recovery + root-token auth
./ci/test_tpm_integration_swtpm.sh       # basic TPM ops + key ops (createprimary/create/sign)
```

Both run automatically via GitHub Actions — see [`.github/workflows/ci-seal-unseal.yml`](../.github/workflows/ci-seal-unseal.yml) and the [Software TPM (swtpm) CI section](#automated-ci-test-citest_seal_unsealsh).

### 8.5 System-level validation

```bash
./system_status.sh
./validate_system.sh
```

---

## 9. Unversioned / Runtime Artifacts

The following paths are generated at runtime by the stack and are intentionally **not committed to version control**. They contain secret material or are ephemeral build artifacts.

| Path | Status | Notes |
|---|---|---|
| `tpm-data/` | **Not versioned — runtime** | TPM-sealed material generated by `vault_initializer.py`; created on first `docker-compose up` |
| `tpm-data/unseal_key_*.enc` (+ `.pub`/`.priv`) | **Not versioned — runtime** | TPM-sealed Shamir unseal keys |
| `tpm-data/root_token.enc` (+ `.pub`/`.priv`) | **Not versioned — runtime** | TPM-sealed Vault root token (no plaintext copy) |
| `tpm-data/app_token.enc` (+ `.pub`/`.priv`) | **Not versioned — runtime** | TPM-sealed least-privilege token, created by `scripts/revoke_root_token.sh` |
| `vault-data/` | **Not versioned — runtime** | Vault storage backend data; persists secrets between restarts |
| `**/venv/` | **Not versioned** | Python virtualenvs — recreate locally; ignored via the root `.gitignore` |
| `.env` | **Not versioned — planned** | Environment variables (TPM handle, shares/threshold, backoff, etc.) |

> **Never commit `tpm-data/` or `vault-data/` to version control.** Both directories contain cryptographic material. A root-level [`.gitignore`](../.gitignore) excludes them (plus `venv/`, `__pycache__/`, `*.log`). If any files were tracked before that rule existed, untrack them with `git rm -r --cached tpm-data vault-data`.

---

## 10. Notes

### TLS in production

Vault currently listens on HTTP (`tls_disable = true` in `vault-config.hcl`). Before any non-local deployment, configure TLS:

```hcl
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}
```

### Production mode (no dev token)

The stack runs Vault in **server/production mode** — there is no `-dev` flag and no default `root` token. Initialization and unsealing are handled entirely by `vault_initializer.py`, with keys sealed in the host TPM. There are **no plaintext `.txt` key dumps**.

### Optional: bind unseal to boot state (PCR policy)

To mitigate evil-maid / offline-tamper scenarios, the seal step can be extended with a **PCR policy** (e.g. `sha256:0,2,4,7`) so `tpm2_unseal` only succeeds when the measured boot state matches. This makes unseal fail after firmware/kernel changes until the blobs are re-sealed — a deliberate trade-off. (Not enabled by default in `vault_initializer.py`.)

### Software TPM (swtpm) for CI/CD

If no physical TPM is available, use `swtpm` to emulate one:

```bash
mkdir /tmp/mytpm
swtpm socket --tpmstate dir=/tmp/mytpm --tpm2 --ctrl type=unixio,path=/tmp/mytpm.sock &
export TPM2TOOLS_TCTI="swtpm:path=/tmp/mytpm.sock"
```

The initializer honors `TPM2TOOLS_TCTI`, so pointing it at the emulator lets you exercise the full seal/unseal flow in CI without physical hardware.

### Automated CI test (`ci/test_seal_unseal.sh`)

The repository ships an end-to-end test that runs the **same** `vault_initializer.py` used in production against a real Vault and an **emulated TPM** (`swtpm`) — no physical hardware required. It validates:

1. The emulated TPM answers (`tpm2_getrandom`).
2. Vault starts **sealed** and **uninitialized**.
3. The initializer runs `sys/init` (5/3), **seals** each unseal key and the root token into the TPM, and **auto-unseals** Vault — producing `*.enc` markers plus `*.enc.pub` / `*.enc.priv` blobs.
4. **No plaintext secrets** are written (no `*.txt`) and the persistent SRK exists at `0x81010001`.
5. Idempotency: a second run with Vault already unsealed is a no-op.
6. **Cross-boot recovery**: Vault is restarted (back to *sealed*) and re-unsealed using **only** the keys recovered from the TPM — proving the persistent SRK survives reboots.

Run it locally (needs `swtpm`, `tpm2-tools`, the `vault` binary, and `python3` with `requests`):

```bash
cd vault-tpm
./ci/test_seal_unseal.sh
```

In CI it runs automatically via GitHub Actions — see [`.github/workflows/ci-seal-unseal.yml`](../.github/workflows/ci-seal-unseal.yml), which installs the dependencies and executes the tests on pushes/PRs that touch `vault-init/`, `ci/`, or `scripts/`.

> **Note:** the seal/unseal steps call `tpm2_flushcontext` after each `tpm2_createprimary` / `tpm2_load` to free transient object slots. Without this, a TPM (physical or emulated) quickly returns `0x902` ("out of memory for object contexts") when sealing multiple shares.

### TPM integration test (`ci/test_tpm_integration_swtpm.sh`)

The CI also runs a swtpm-based TPM integration test covering basic TPM operations (`properties-fixed`, PCR read, `getrandom`) and key operations (`createprimary` / `create` / `sign`).

> **Limitation — by design for the VM/CI environment:** the original [`test_tpm_integration.sh`](test_tpm_integration.sh) targets a running `docker-compose` stack with a **physical TPM** exposed as `/dev/tpmrm0` inside the containers, and probes a Vault **TPM auth method** (`auth/tpm/roles`) that is *not* part of this seal/unseal design. A standard CI runner (and a plain VM) has neither a physical TPM device nor that auth backend, so that script is **not** executed in CI. Since the whole project is meant to be demonstrated inside a **virtual machine**, CI validates the applicable parts through the emulated TPM (`swtpm`) instead. Run the original `test_tpm_integration.sh` only on a host with a real TPM and the full stack up (`docker-compose up -d`).


*Part of the [app-tpm](https://github.com/juarez1972/app-tpm) project — PPGIa/PUCPR, Brazil.*
