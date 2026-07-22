# IaC — Terraform Provisioning (app-tpm)

![project](https://img.shields.io/badge/project-app--tpm-1f6feb?logo=github)
![Terraform](https://img.shields.io/badge/Terraform-%E2%89%A51.6-7B42BC?logo=terraform)
![HashiCorp Vault](https://img.shields.io/badge/Vault-KV%20v2-000000?logo=vault)
![Twingate](https://img.shields.io/badge/ZTNA-Twingate-6C47FF)
![license](https://img.shields.io/badge/license-MIT-green)

This directory provisions the **entire** hybrid Zero-Trust stack as code. Nothing
is configured by hand: Vault mounts and policies, per-device TOTP seeds, the
Docker Compose runtime, the Twingate ZTNA resources, and the Intel SGX
confidential-compute node are all declared in Terraform and reconciled with
`terraform apply`. Adding a device or changing a protection tier is a code
change, not a manual procedure.

> **Planning artifact.** These modules describe the target infrastructure. They
> are intended to be reviewed and applied against live Vault / Docker / Twingate
> backends; they are not exercised in the CI sandbox.

---

## 1. Layout

```
iac/
├── versions.tf              # Provider requirements (vault, docker, twingate, null, random)
├── modules/
│   ├── vault-tpm/           # KV v2 mount, app-policy, AppRole for the IoT server
│   ├── iot-devices/         # Per-device TOTP seed in Vault + TPM sealing hook
│   ├── compose-stack/       # Runtime containers (Vault, IoT server, connector)
│   ├── ztna/                # Twingate remote network, resources, access group
│   └── sgx-node/            # SGX (Gramine) node for the Vault initializer
└── envs/
    ├── ppgia96/             # Production (includes a critical-tier device -> SGX)
    └── ppgia95/             # Validation / staging (no critical tier -> no SGX)
```

---

## 2. Sensitivity tiers → hardware protection

Each device carries a `tier` that the IaC maps to a hardware protection level.
This is the mechanism the paper refers to as "tiers assigned automatically by
IaC":

| Tier       | Hardware protection                          | Provisioned by            |
| ---------- | -------------------------------------------- | ------------------------- |
| `standard` | TPM 2.0 sealing (SRK, PCR 0/7)               | `iot-devices`             |
| `high`     | TPM + Intel SGX enclave (Gramine)            | `iot-devices` + `sgx-node`|
| `critical` | SGX-shielded Vault initializer + Intel TDX   | `sgx-node` (enabled)      |

The SGX node is provisioned only when at least one `critical` device is present
(`local.has_critical`), so validation environments stay lightweight.

---

## 3. Modules

- **`vault-tpm`** — enables the KV v2 engine (mount `secret`), creates
  `app-policy` scoped to `secret/data/tpm-verified/*`, and (optionally) an
  AppRole `iot-server` so the server never uses the root token. The root token
  itself stays **TPM-sealed** and never enters Terraform state.
- **`iot-devices`** — for each entry in the `devices` map, writes
  `otp_secret` to `secret/data/tpm-verified/iot/devices/<id>` and can trigger
  `iot-tpm/scripts/init_device.sh` to seal the seed in the device TPM
  (`run_tpm_sealing`, off by default so CI never touches a device).
- **`compose-stack`** — launches Vault (production mode, `IPC_LOCK`) and the IoT
  auth server via the Docker provider, enforcing `OTP_MODE=hmac`.
- **`ztna`** — declares the Twingate remote network, the Vault and IoT-server
  resources (no inbound port), the access group, and the connector tokens
  consumed by the on-prem connector container.
- **`sgx-node`** — runs the Vault initializer inside an Intel SGX enclave
  (Gramine), mounting `/dev/sgx_enclave`, `/dev/sgx_provision`, and the AESM
  socket for DCAP remote attestation. See [`../sgx/README.md`](../sgx/README.md).

---

## 4. Usage

Set the backend credentials via environment variables (never in committed files):

```bash
export VAULT_ADDR="https://vault.internal.ppgia96:8200"
export VAULT_TOKEN="<app-policy-scoped-token>"      # NOT the root token
export TWINGATE_API_TOKEN="<twingate-api-token>"
export TWINGATE_NETWORK="<your-twingate-network>"

cd iac/envs/ppgia96
terraform init
terraform plan
terraform apply
```

Switch `ppgia96` for `ppgia95` to target the validation environment.

---

## 5. State security

Terraform state can contain device seeds and connector tokens. The provided
`.gitignore` excludes all `*.tfstate*` and `*.tfvars`. In production, configure
an **encrypted remote backend** (e.g. an encrypted object store) via
`terraform init -backend-config=...` rather than the local backend shown in the
environment files.

---

## 6. Relationship to the other modules

- `vault-tpm/` (repo) — provides the TPM-sealed Vault this IaC configures.
- `iot-tpm/` (repo) — provides `init_device.sh` and the HMAC-envelope agents.
- `ztna/` (repo) — the connector container this IaC pairs with Twingate Cloud.
- `sgx/` (repo) — the Gramine enclave image the `sgx-node` module deploys.
