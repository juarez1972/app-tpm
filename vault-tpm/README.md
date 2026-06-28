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

`vault-tpm` addresses the **Secret Zero problem** in Infrastructure as Code: how to bootstrap secret management without storing an initial plaintext credential anywhere. The solution anchors the Vault unseal key inside a TPM 2.0 — a dedicated tamper-resistant chip that can only release the key when PCR measurements match the expected, untampered boot state.

**Key capabilities:**

- TPM 2.0-based hardware validation before every Vault unseal
- Automated container orchestration: the TPM validator runs first, Vault only starts after the check passes
- Web health endpoint (port 8080) served by `tpm-validator/tpm_validator.py` for external monitoring
- Vault policies enforcing minimum-privilege access for any service interacting with secrets
- Utility scripts for system status checks and integration testing

**Port summary:**

| Service | Port | Protocol |
|---|---|---|
| HashiCorp Vault API | `8200` | HTTP (add TLS before production) |
| TPM Validator health endpoint | `8080` | HTTP |

---

## 2. Architecture

The stack consists of three containers orchestrated by Docker Compose. The startup sequence enforces a strict dependency order: the TPM validator must pass before the vault initializer runs, and the vault initializer must complete successfully before Vault serves any requests.

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
│  │                       │     │  1. Validates TPM is alive     │     │
│  │  • Monitors TPM state │     │  2. Encrypts unseal keys       │     │
│  │  • Checks .enc files  │     │     with TPM → saves .enc      │     │
│  │  • Checks Vault health│     │  3. Unseals Vault via PKCS#11  │     │
│  │  • Exposes port 8080  │     │                                │     │
│  └───────────┬───────────┘     └───────────────┬───────────────┘     │
│              │  health check                    │  init complete      │
│              │                                  ▼                     │
│              │                    ┌─────────────────────────┐         │
│              │                    │     HashiCorp Vault      │         │
│              │                    │                          │         │
│              └───────────────────►│  Sealed at boot          │         │
│                 continuous        │  Unsealed only after     │         │
│                 monitoring        │  TPM validation passes   │         │
│                                   │                          │         │
│                                   │  Port 8200               │         │
│                                   └──────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘

Boot sequence:
  Boot → TPM Validation → Vault Init (encrypt + unseal) → Vault Operational
```

**Startup sequence:**

1. Docker Compose brings up `tpm-validator` first; it verifies TPM accessibility and health.
2. `vault-init` starts next: `vault_initializer.py` encrypts Vault's unseal keys using the TPM and stores the resulting `.enc` files in the `tpm-data/` volume (not versioned).
3. HashiCorp Vault starts and is unsealed using the TPM-decrypted key material.
4. `tpm-validator` continues running, periodically checking the TPM state, `.enc` files, and Vault health, and exposing results on port 8080.

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
│   └── setup_vault_policies.hcl   # Minimum-privilege Vault access policies (HCL)
│
├── templates/
│   └── index.html                  # Web UI template served by tpm-validator
│
├── tpm-validator/
│   ├── Dockerfile                  # Container image (x86_64 / amd64)
│   ├── Dockerfile.debian           # Debian-based variant
│   ├── tpm_validator.py            # Main health-check service (port 8080)
│   ├── health_check.py             # TPM and Vault health-check helper
│   └── requirements.txt            # Python dependencies for this service
│
├── vault-init/
│   ├── Dockerfile                  # Container image (x86_64 / amd64)
│   ├── Dockerfile.debian           # Debian-based variant
│   ├── vault_initializer.py        # Vault initializer: TPM encrypt → unseal
│   └── requirements.txt            # Python dependencies for this service
│
├── setup_secret.sh                 # Helper script: writes an example secret into Vault
├── system_status.sh                # Displays overall stack health (TPM, Vault, containers)
├── test_tpm_integration.sh         # End-to-end TPM ↔ Vault integration test suite
└── validade_system.sh              # System validation script (filename is as in the repo)
```

**Notes on unversioned / runtime artifacts** — see [Section 9](#9-unversioned--runtime-artifacts).

---

## 4. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | 24.0+ | Required |
| Docker Compose | v2.x | Required |
| Python | 3.10+ | For running scripts outside containers |
| TPM 2.0 | — | Physical chip (e.g., Infineon SLB9670) or software emulator (`swtpm`) |
| `tpm2-tools` | 5.x | Must be installed on the host |
| `tpm2-pytss` | latest | Python bindings for TPM 2.0 TSS |

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

### 5.3 Development token

In development mode (`VAULT_DEV_ROOT_TOKEN_ID=root`), the default Vault root token is `root`. **Remove dev mode and use TPM-only auto-unseal in any production deployment.**

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

Docker Compose starts the three services in dependency order: `tpm-validator` → `vault-init` → `vault`.

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

`setup_secret.sh` authenticates to Vault, creates the target KV path, and writes a sample key-value pair — useful for verifying that the unseal flow completed successfully and that write access is functioning.

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
| `vault` | `hashicorp/vault` | `8200` | Secret store — only starts after TPM validation |
| `vault-init` | `vault-init/Dockerfile` | — | Encrypts unseal keys via TPM; initializes Vault |
| `tpm-validator` | `tpm-validator/Dockerfile` | `8080` | Continuous health monitor: TPM + `.enc` files + Vault |

### 7.2 `vault-init/vault_initializer.py`

Orchestrates the secure initialization sequence:

1. Connects to the host TPM via `tpm2-pytss`.
2. Generates Vault unseal keys and encrypts them using the TPM public key — the resulting `.enc` files are written to the `tpm-data/` volume.
3. Unseals Vault by decrypting the key material inside the TPM (the plaintext key is never written to disk).
4. In development mode, a plaintext `.txt` copy is also written for debugging. **Remove this in production.**

### 7.3 `tpm-validator/tpm_validator.py`

Runs as a long-lived service that:

- Periodically checks TPM accessibility (via `tpm2_getrandom` or equivalent).
- Verifies that the expected `.enc` files are present in the `tpm-data/` volume.
- Polls the Vault health endpoint (`GET /v1/sys/health`).
- Exposes all results on port **8080** via an HTTP health endpoint — the `templates/index.html` provides a simple web dashboard for this data.

### 7.4 `tpm-validator/health_check.py`

Helper module called by `tpm_validator.py`. Encapsulates individual health-check functions for the TPM subsystem and Vault API, keeping the main service file focused on HTTP serving and scheduling.

### 7.5 `scripts/setup_vault_policies.hcl`

HCL policy definitions for minimum-privilege Vault access. Referenced in the root README (Section 6.2) as part of the broader secret lifecycle. Apply after initialization using the Vault CLI (see [Section 5.2](#52-access-policies----scriptssSetup_vault_policieshcl)).

### 7.6 `vault-config.hcl`

Vault server configuration file: defines the storage backend, TCP listener, and public API address. Mounted into the `vault` container at startup. See [Section 5.1](#51-vault-server----vault-confighcl) for details.

### 7.7 Shell scripts

| Script | Purpose |
|---|---|
| `system_status.sh` | Queries and prints the health of all three containers, the TPM device, and Vault |
| `test_tpm_integration.sh` | End-to-end integration tests: TPM read, Vault write, Vault read, health checks |
| `setup_secret.sh` | Writes an example secret to Vault — useful for smoke-testing after initialization |
| `validade_system.sh` | Full system validation script (note: filename in the repository is `validade_system.sh`, not `validate_system.sh`) |

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
./test_tpm_integration.sh
```

The test suite covers:

- Real-time TPM validation
- Inter-container communication
- Vault write and read operations
- Data persistence across container restarts
- Automatic recovery after Vault restart
- Continuous health check operation

### 8.5 System-level validation

```bash
./system_status.sh
./validade_system.sh
```

---

## 9. Unversioned / Runtime Artifacts

The following paths are generated at runtime by the stack and are intentionally **not committed to version control**. They contain secret material or are ephemeral build artifacts.

| Path | Status | Notes |
|---|---|---|
| `tpm-data/` | **Not versioned — runtime** | Sealed unseal keys (`*.enc`) and root token generated by `vault_initializer.py`; created on first `docker-compose up` |
| `tpm-data/secret` | **Not versioned — runtime** | Encrypted Vault unseal key |
| `tpm-data/vault-root-key` | **Not versioned — runtime** | Encrypted Vault root token |
| `vault-data/` | **Not versioned — runtime** | Vault storage backend data; persists secrets between restarts |
| `.env` | **Not versioned — planned** | Environment variables (Vault token, TPM paths, etc.) |

> **Never commit `tpm-data/` or `vault-data/` to version control.** Both directories contain cryptographic material. Ensure they are listed in `.gitignore`.

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

### Removing development mode

The `vault-init` container uses `VAULT_DEV_ROOT_TOKEN_ID=root` for local testing. In production:

1. Remove the `VAULT_DEV_ROOT_TOKEN_ID` environment variable from `docker-compose.yml`.
2. Remove any plaintext `.txt` key dumps in `vault_initializer.py`.
3. Use Vault's native auto-unseal via PKCS#11 pointing to the TPM.

### Software TPM (swtpm) for CI/CD

If no physical TPM is available, use `swtpm` to emulate one:

```bash
mkdir /tmp/mytpm
swtpm socket --tpmstate dir=/tmp/mytpm --tpm2 --ctrl type=unixio,path=/tmp/mytpm.sock &
export TPM2TOOLS_TCTI="swtpm:path=/tmp/mytpm.sock"
```

### Dockerfile variants

Both `vault-init/` and `tpm-validator/` include a standard `Dockerfile` and a `Dockerfile.debian`. The Debian variants may be preferred in environments where Alpine-based images cause `glibc`/`musl` compatibility issues with TPM libraries.

---

*Part of the [app-tpm](https://github.com/juarez1972/app-tpm) project — PPGIa/PUCPR, Brazil.*
