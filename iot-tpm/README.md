# IoT-TPM: Non-Interactive Authentication Agent with TPM 2.0

![app-tpm](https://img.shields.io/badge/project-app--tpm-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Docker](https://img.shields.io/badge/docker-required-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> Component of the prototype described in:
> **"A Hybrid Zero Trust Architecture for Non-Interactive Authentication"**
> Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. — PPGIa/PUCPR, Brazil.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Prerequisites](#4-prerequisites)
5. [Initial Setup](#5-initial-setup)
6. [Execution](#6-execution)
7. [Communication Protocols](#7-communication-protocols)
8. [Security Model](#8-security-model)
9. [Certificate Generation](#9-certificate-generation)
10. [Troubleshooting](#10-troubleshooting)
11. [References](#11-references)

---

## 1. Overview

`iot-tpm` implements a **non-interactive authentication agent** for IoT devices using a **TPM 2.0** (Trusted Platform Module) chip. The module enables an IoT device to prove its identity to a server without any human interaction, using keys sealed to the TPM's PCR registers.

**Key capabilities:**

- TPM 2.0-based hardware identity (sealed keys bound to PCR registers)
- Support for two communication protocols: **REST API** (HTTPS) and **MQTT** (TLS)
- Automatic unsealing and startup via `unseal_and_start.py`
- Containerized deployment for both server and client components

**Use case:** Edge devices (e.g., Raspberry Pi with TPM 2.0) that must authenticate to a backend server at boot time, without a password prompt or human operator.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         IoT Device                              │
│                                                                 │
│  ┌──────────────────┐        ┌───────────────────────────────┐  │
│  │    TPM 2.0        │        │      client-iot/              │  │
│  │  ┌─────────────┐ │        │  ┌─────────────────────────┐  │  │
│  │  │ sealed_key  │ │◄──────►│  │  client_rest_api/        │  │  │
│  │  │  .pub/.priv │ │        │  │  client_iot.py           │  │  │
│  │  └─────────────┘ │        │  └─────────────────────────┘  │  │
│  │                  │        │  ┌─────────────────────────┐  │  │
│  └──────────────────┘        │  │  client_mqtt/            │  │  │
│                              │  │  client_mqtt.py          │  │  │
│  ┌──────────────────┐        │  └─────────────────────────┘  │  │
│  │ unseal_and_       │        └───────────────────────────────┘  │
│  │ start.py          │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │ HTTPS / MQTT+TLS              │
              ▼                               ▼
┌─────────────────────┐         ┌─────────────────────────┐
│  server_rest_api/   │         │    server_mqtt/          │
│  server_rest_api.py │         │    server_mqtt.py        │
│  main.py            │         │    mosquitto.conf        │
│  (FastAPI/Uvicorn)  │         │    (Mosquitto broker +   │
│                     │         │     Python subscriber)   │
└─────────────────────┘         └─────────────────────────┘
```

**Authentication flow:**

1. On boot, `unseal_and_start.py` instructs the TPM to unseal the private key (only possible if PCR values match the expected boot state).
2. The client signs a challenge (or presents its TLS certificate derived from the sealed key) to the server.
3. The server validates the signature / certificate chain and grants access.
4. If PCR values have changed (e.g., due to firmware tampering), unsealing fails and the device cannot authenticate.

---

## 3. Directory Structure

```
iot-tpm/
├── unseal_and_start.py          # Entry point: unseals TPM key and launches client
├── Dockerfile                   # Container image for the IoT agent
├── README.md
│
├── client-iot/
│   ├── client_rest_api/
│   │   ├── client_iot.py        # REST API client (HTTPS + TPM auth)
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── certs/
│   │           └── gerar_certificados.py  # TLS cert generation for REST client
│   │
│   └── client_mqtt/
│       ├── client_mqtt.py       # MQTT client (TOTP loop; secret unsealed from TPM)
│       ├── scripts/
│       │   └── init_device.sh   # Device provisioning: generate secret, seal in TPM, register in Vault
│       ├── Dockerfile           # Container image for MQTT client
│       ├── Dockerfile.arm64     # ARM64 variant (e.g., Raspberry Pi)
│       ├── docker-compose.yml
│       ├── .env.example         # Sample client configuration
│       └── requirements.txt
│
└── server/
    ├── gerar_certificados.py    # TLS cert generation for server (CA, server cert/key)
    │
    ├── server_rest_api/
    │   ├── main.py              # Application entry point (Uvicorn startup)
    │   ├── server_rest_api.py   # FastAPI route handlers
    │   ├── docker-compose.yml
    │   └── requirements.txt
    │
    └── server_mqtt/
        ├── server_mqtt.py       # MQTT subscriber: validates TOTP, reads secret from Vault
        ├── mosquitto.conf       # Mosquitto broker configuration (TLS listener 8883)
        ├── Dockerfile
        ├── docker-compose.yml
        ├── .env.example         # Sample server configuration (incl. Vault)
        └── requirements.txt
```

**Notes on unversioned / local-only paths:**

| Path | Status | Notes |
|---|---|---|
| `iot-tpm/sealed_key.pub` | **Not versioned** | Generated locally by the TPM seal operation |
| `iot-tpm/sealed_key.priv` | **Not versioned** | Generated locally by the TPM seal operation |
| `iot-tpm/certs/` | **Not versioned / planned** | Runtime TLS certificates |
| `iot-tpm/data/` | **Not versioned / planned** | Runtime data storage |
| `iot-tpm/logs/` | **Not versioned / planned** | Runtime logs |
| `iot-tpm/.env` | **Not versioned / planned** | Environment variables (secrets) |
| `server/certs/` | **Not versioned** | Generated by `server/gerar_certificados.py` — contains `ca.crt`, `server.crt`, `server.key` |

---

## 4. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | |
| Docker | 24.0+ | Required for containerized deployment |
| Docker Compose | v2.x | |
| TPM 2.0 | — | Physical chip or software emulator (e.g., `swtpm`) |
| `tpm2-tools` | 5.x | Must be installed on the host |
| `tpm2-pytss` | latest | Python bindings for TPM 2.0 TSS |
| OpenSSL | 3.x | Certificate generation |

**Operating system:** Linux (tested on Ubuntu 22.04 and Raspberry Pi OS Bookworm).

---

## 5. Initial Setup

### 5.1 Clone the repository

```bash
git clone https://github.com/<owner>/app-tpm.git
cd app-tpm/iot-tpm
```

### 5.2 Install Python dependencies (host / development)

```bash
# REST API client
pip install -r client-iot/client_rest_api/requirements.txt

# MQTT client
pip install -r client-iot/client_mqtt/requirements.txt

# REST API server
pip install -r server/server_rest_api/requirements.txt

# MQTT server
pip install -r server/server_mqtt/requirements.txt
```

### 5.3 Generate TLS certificates

Generate the server-side certificates first (CA + server cert/key):

```bash
cd iot-tpm/server/
python gerar_certificados.py
```

This creates `server/certs/` (unversioned) containing `ca.crt`, `server.crt`, and `server.key`.

For the REST API client's TLS certificates, a dedicated script is also available:

```bash
cd iot-tpm/client-iot/client_rest_api/app/certs/
python gerar_certificados.py
```

### 5.4 Seal the TPM key

```bash
cd iot-tpm/
# Create primary key and seal private key to current PCR state
tpm2_createprimary -C e -g sha256 -G ecc -c primary.ctx
tpm2_create -G rsa2048 -u sealed_key.pub -r sealed_key.priv -C primary.ctx \
    -L "pcr:sha256:0,1,2,3,4,7"
```

> `sealed_key.pub` and `sealed_key.priv` are generated locally and **must not be committed to version control**.

### 5.5 Configure environment variables

Create `iot-tpm/.env` (unversioned):

```dotenv
SERVER_HOST=192.168.1.100
SERVER_PORT=8443
MQTT_BROKER_HOST=192.168.1.100
MQTT_BROKER_PORT=8883
TPM_PCR_BANK=sha256
TPM_PCR_LIST=0,1,2,3,4,7
```

---

## 6. Execution

All commands below assume the working directory is `iot-tpm/` unless otherwise stated.

### 6.1 Unseal and start (recommended entry point)

```bash
cd iot-tpm/
python unseal_and_start.py
```

This script:
1. Instructs the TPM to unseal `sealed_key.priv` using the current PCR values.
2. Launches the appropriate client (REST or MQTT, depending on configuration).
3. If unsealing fails (PCR mismatch), the script exits with an error — no credentials are exposed.

### 6.2 REST API server

#### Run directly

```bash
cd iot-tpm/
python server/server_rest_api/main.py
```

#### Run with Docker Compose

```bash
cd iot-tpm/server/server_rest_api/
docker-compose up --build
```

### 6.3 MQTT server (Mosquitto + subscriber)

The subscriber reads each device's TOTP secret from **HashiCorp Vault** (the
`vault-tpm` project), keyed by `device_id`, and validates the code. Configure
`VAULT_ADDR` / `VAULT_TOKEN` in `.env` (see `.env.example`). Without a reachable
Vault it falls back to a single `OTP_SECRET` from `.env` (development only).

#### Run directly

```bash
cd iot-tpm/server/server_mqtt/
cp .env.example .env    # ajuste VAULT_ADDR, VAULT_TOKEN, etc.
python server_mqtt.py
```

#### Run with Docker Compose (broker + subscriber)

```bash
cd iot-tpm/server/server_mqtt/
docker compose up --build
```

### 6.4 REST API client

```bash
cd iot-tpm/
python client-iot/client_rest_api/client_iot.py
```

### 6.5 MQTT client

> **Provision the device first.** The client does not hold its OTP secret in
> `.env` in production — the secret is **sealed in the device's TPM** and
> **registered in the server's Vault**. Run the provisioning script once per
> device before starting the client:
>
> ```bash
> cd iot-tpm/client-iot/client_mqtt/
> DEVICE_ID=device-001 \
>   VAULT_ADDR=http://<server-ip>:8200 VAULT_TOKEN=<app_token> \
>   ./scripts/init_device.sh
> ```
>
> This generates a per-device Base32 TOTP secret, seals it in the TPM
> (`tpm-data/<DEVICE_ID>_otp.enc.pub/.priv`, never written to disk in
> plaintext) and writes it to the server's Vault at
> `secret/data/tpm-verified/iot/devices/<DEVICE_ID>` (field `otp_secret`).
> Omit `VAULT_TOKEN` to seal only in the TPM and register in Vault manually.
> See [Section 8](#8-security-model) for the secret lifecycle.

#### Run directly

```bash
cd iot-tpm/client-iot/client_mqtt/
DEVICE_ID=device-001 python client_mqtt.py
```

The client recovers the sealed secret from the TPM into memory, then publishes
a fresh TOTP code every `OTP_INTERVAL` seconds (default 60). If the TPM is
unavailable it falls back to `OTP_SECRET` from `.env` (development only).

#### Run with Docker Compose (x86_64)

```bash
cd iot-tpm/client-iot/client_mqtt/
cp .env.example .env   # ajuste DEVICE_ID, MQTT_BROKER, etc.
docker compose --profile dev up --build
```

The compose file mounts `./tpm-data` (sealed blobs) and `/dev/tpmrm0` into the
container so the client can unseal its secret at startup.

#### Run with Docker (ARM64 — e.g., Raspberry Pi)

```bash
cd iot-tpm/client-iot/client_mqtt/
docker compose --profile arm64 up --build
```

### 6.6 Full IoT agent (Docker)

The root-level `Dockerfile` packages the entire IoT agent:

```bash
cd iot-tpm/
docker build -t iot-tpm-agent .
docker run --rm \
  --device /dev/tpm0 \
  --device /dev/tpmrm0 \
  -v "$(pwd)/sealed_key.pub:/app/sealed_key.pub:ro" \
  -v "$(pwd)/sealed_key.priv:/app/sealed_key.priv:ro" \
  --env-file .env \
  iot-tpm-agent
```

---

## 7. Communication Protocols

### 7.1 REST API (HTTPS)

| Item | Value |
|---|---|
| Default port | `8443` |
| TLS | Mutual TLS (mTLS) |
| Authentication endpoint | `POST /auth` |
| Payload | JSON with TPM-signed challenge |
| Server framework | FastAPI + Uvicorn |

**Authentication sequence:**

```
Client                                 Server
  │                                      │
  │──── POST /auth {device_id, sig} ────►│
  │                                      │ verify sig against TPM pub key
  │◄─── 200 OK {token} ─────────────────│
  │                                      │
```

### 7.2 MQTT (TLS)

| Item | Value |
|---|---|
| Default port | `8883` (TLS) |
| TLS | Server TLS via `mosquitto.conf` (mTLS optional — `require_certificate`) |
| Broker | Eclipse Mosquitto (configured via `mosquitto.conf`) |
| Verify topic | `iot/verify` (env `MQTT_TOPIC_VERIFY`) |
| Response topic | `iot/response/{device_id}` |
| MFA | TOTP (`pyotp`, `OTP_INTERVAL` seconds, default 60) |
| Client secret source | Sealed in the device **TPM** (unsealed to RAM at start) |
| Server secret source | **HashiCorp Vault** KV v2, keyed by `device_id` (fallback `.env`) |
| Server handler | `server_mqtt.py` (Python subscriber) |

**Authentication sequence:**

```
Device (client_mqtt.py)          Mosquitto Broker        server_mqtt.py
  │  unseal OTP secret from TPM        │                      │  read OTP secret from
  │  (RAM only)                        │                      │  Vault by device_id
  │──── CONNECT (TLS) ────────────────►│                      │
  │◄─── CONNACK ───────────────────────│                      │
  │── PUBLISH iot/verify {id, otp} ───►│──── message ────────►│
  │                                    │                      │ totp.verify(otp)
  │◄─ PUBLISH iot/response/{id} ───────│◄─── {status} ────────│
  │     {status: valid|invalid}        │                      │
```

> **Consistency requirement:** `OTP_INTERVAL` must match on client and server,
> otherwise every code is rejected. Keep it identical in both `.env` files.

---

## 8. Security Model

### 8.1 TPM Key Sealing

Keys are sealed against a set of PCR (Platform Configuration Register) values that reflect the device's measured boot state:

| PCR | Measures |
|---|---|
| PCR 0 | Core UEFI firmware |
| PCR 1 | UEFI firmware configuration |
| PCR 2 | Option ROMs |
| PCR 3 | Option ROM configuration |
| PCR 4 | Boot manager code |
| PCR 7 | Secure Boot state |

If any of these values change (e.g., firmware update, Secure Boot disabled, or OS tampering), the TPM will refuse to unseal the key — the device loses the ability to authenticate until the key is re-sealed by an authorized operator.

### 8.1.1 MQTT device secret lifecycle (TOTP + Vault + TPM)

For the MQTT flow, the shared secret is a per-device **TOTP** seed handled as
follows:

1. **Provisioning** (`scripts/init_device.sh`, once per device): a random
   Base32 secret is generated in RAM, **sealed in the device's TPM** under the
   persistent SRK (`0x81010001`) as `tpm-data/<device_id>_otp.enc.pub/.priv`,
   and **written to the server's Vault** at
   `secret/data/tpm-verified/iot/devices/<device_id>` (field `otp_secret`,
   covered by the `app-policy` from the `vault-tpm` project). The plaintext
   secret never touches disk.
2. **Client runtime**: `client_mqtt.py` unseals the secret from the TPM into
   memory (`tpm2_load` + `tpm2_unseal`) and derives TOTP codes. If PCR/boot
   state changed, the unseal fails and the device cannot authenticate.
3. **Server runtime**: `server_mqtt.py` reads the same secret from Vault by
   `device_id`, caches it in memory, and validates each TOTP code.

> The secret is never held in plaintext on disk on either side. The `.env`
> `OTP_SECRET` is a **development-only** fallback for both components.

### 8.2 Threat Mitigations

| Threat | Mitigation |
|---|---|
| Key theft (software) | Private key never leaves the TPM; only the TPM can perform operations with it |
| Firmware tampering | PCR-based sealing detects measurement changes |
| Replay attacks | Challenge-response with nonces; TLS record layer |
| MITM | mTLS (REST) / TLS with client certificates (MQTT) |
| Credential exposure | `.env` and `sealed_key.*` are unversioned and never committed |

### 8.3 Zero Trust Assumptions

This module implements the **device identity** pillar of the hybrid Zero Trust architecture described in the referenced paper. It does **not** implement:

- Network micro-segmentation (handled at the infrastructure layer)
- User identity federation (handled by a separate module)
- Policy decision point (handled by the server-side trust engine)

---

## 9. Certificate Generation

Two certificate generation scripts are included:

### 9.1 Server-side certificates (CA + server cert/key)

```bash
cd iot-tpm/server/
python gerar_certificados.py
```

Generates under `server/certs/` (unversioned):

| File | Description |
|---|---|
| `ca.crt` | Self-signed CA certificate |
| `server.crt` | Server certificate signed by the CA |
| `server.key` | Server private key |

### 9.2 REST client TLS certificates

A second script handles certificate generation specifically for the REST API client:

```bash
cd iot-tpm/client-iot/client_rest_api/app/certs/
python gerar_certificados.py
```

This produces the client-side certificates needed for mTLS with the REST API server. The output files are stored locally under `client-iot/client_rest_api/app/certs/` and are **not versioned**.

### 9.3 Distribution

After generation, distribute the CA certificate to clients (for REST) and configure Mosquitto with the CA, server cert, and server key (for MQTT). See `server/server_mqtt/mosquitto.conf` for the broker TLS configuration directives.

---

## 10. Troubleshooting

### TPM device not found

```
Error: /dev/tpm0: No such file or directory
```

**Solution:** Verify that the TPM driver is loaded (`ls /dev/tpm*`) and that the container is started with `--device /dev/tpm0 --device /dev/tpmrm0`.

### PCR mismatch / unsealing failure

```
Error: TPM2_CC_Unseal failed: TPM_RC_POLICY_FAIL
```

**Solution:** The device's PCR values no longer match those recorded at sealing time. Common causes: firmware update, Secure Boot configuration change, kernel update that alters measured boot. An authorized operator must re-seal the key against the new PCR state.

### MQTT TLS handshake failure

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:** Ensure `ca.crt` is correctly referenced in the client configuration and that the server certificate was signed by the same CA. Regenerate certificates if the CA has changed (see [Section 9](#9-certificate-generation)).

### REST API 401 Unauthorized

**Possible causes:**

1. TPM signature verification failed — check that `sealed_key.pub` matches the key used to sign the challenge.
2. Challenge nonce expired — synchronize clocks between client and server (use NTP).
3. mTLS client certificate not presented — verify `client_iot.py` is loading the correct certificate path.

### Docker permission denied on TPM device

```
open /dev/tpm0: permission denied
```

**Solution:** Add the user to the `tss` group on the host:

```bash
sudo usermod -aG tss $USER
# Log out and back in, then re-run Docker
```

---

## 11. References

1. Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. **"A Hybrid Zero Trust Architecture for Non-Interactive Authentication"**. PPGIa/PUCPR, Brazil.
2. [TPM 2.0 Library Specification — Trusted Computing Group](https://trustedcomputinggroup.org/resource/tpm-library-specification/)
3. [tpm2-tools documentation](https://tpm2-tools.readthedocs.io/)
4. [tpm2-pytss — Python TSS bindings](https://github.com/tpm2-software/tpm2-pytss)
5. [Eclipse Mosquitto MQTT broker](https://mosquitto.org/)
6. [FastAPI documentation](https://fastapi.tiangolo.com/)
7. [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final)

---

*Part of the [app-tpm](../README.md) project — PPGIa/PUCPR, Brazil.*
