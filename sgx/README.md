# SGX — Confidential Vault Initializer (Intel SGX / Gramine)

![project](https://img.shields.io/badge/project-app--tpm-1f6feb?logo=github)
![Intel SGX](https://img.shields.io/badge/Intel-SGX-0071C5?logo=intel)
![Gramine](https://img.shields.io/badge/Gramine-LibOS-4B0082)
![Attestation](https://img.shields.io/badge/Attestation-DCAP-2E7D32)
![license](https://img.shields.io/badge/license-MIT-green)

This directory provisions the **confidential-compute tier** of the hybrid
Zero-Trust architecture. It runs the single most sensitive secret-handling
script — the **Vault initializer** (`vault-tpm/vault-init/vault_initializer.py`)
— inside an **Intel SGX enclave** using **Gramine**, so the Vault unseal shares
and root token are processed only in CPU-encrypted enclave memory.

> **Planning artifact.** These files describe the enclave build and deployment.
> They target real SGX hardware (FLC-capable CPU + DCAP) and are not exercised
> in the CI sandbox.

---

## 1. Why the initializer (and only the initializer)

The initializer is where Secret Zero briefly lives in RAM: it unseals the Shamir
shares from the TPM and submits them to `sys/unseal`, and it handles the root
token. Everywhere else in the architecture the secret is either sealed in the
TPM (device seeds) or encrypted at rest in Vault. Shielding just the initializer
keeps the **trusted computing base minimal**: the smaller the enclave, the
smaller the `MRENCLAVE` a verifier must trust.

The IoT REST/MQTT servers are intentionally **not** placed in an enclave —
they only read short-lived device seeds via the scoped `app-policy`, and adding
them would enlarge the TCB without protecting Secret Zero.

| Component                       | Protection                    | In enclave? |
| ------------------------------- | ----------------------------- | ----------- |
| Device TOTP seed                | TPM sealing (device)          | n/a         |
| Vault data at rest              | Vault encryption              | no          |
| **Vault initializer (Secret 0)**| **SGX enclave (this dir)**    | **yes**     |
| IoT REST/MQTT server            | app-policy scoped token       | no          |

---

## 2. What the enclave guarantees

- **Memory confidentiality/integrity** — enclave pages are encrypted by the CPU;
  a compromised kernel, hypervisor, or co-tenant cannot read the unseal shares
  or root token.
- **Measured boot of the code** — `sgx.trusted_files` fixes the initializer and
  its runtime into `MRENCLAVE`; any tampering changes the measurement.
- **Remote attestation (DCAP)** — a verifier confirms the exact enclave identity
  before releasing/accepting material, using the AESM quote-generation socket.

---

## 3. Files

| File                                     | Purpose                                              |
| ---------------------------------------- | ---------------------------------------------------- |
| `vault_initializer.manifest.template`    | Gramine manifest: entrypoint, mounts, SGX sizing, trusted files, DCAP. |
| `Dockerfile.gramine`                     | Builds on `gramineproject/gramine`, renders + signs the manifest. |
| `requirements.txt`                       | Initializer deps (mirrors `vault-tpm/vault-init`).   |

The TPM resource manager (`/dev/tpmrm0`) is passed through so the enclave can
read the sealed shares; the device is mounted read-through, not measured.

---

## 4. Build

The build context must include the initializer source. From the repo root:

```bash
cp vault-tpm/vault-init/vault_initializer.py sgx/vault_initializer.py
cd sgx
docker build -f Dockerfile.gramine -t app-tpm/vault-initializer-sgx:latest .
```

The build renders the manifest with `gramine-manifest`, signs it with
`gramine-sgx-sign`, and prints the sigstruct (including `MRENCLAVE`/`MRSIGNER`)
via `gramine-sgx-sigstruct-view` so you can record the expected measurement for
your attestation policy.

---

## 5. Deploy (via IaC)

The [`iac/modules/sgx-node`](../iac/modules/sgx-node/main.tf) module deploys this
image, mounting the SGX devices and the AESM socket:

```
/dev/sgx_enclave        # enclave creation
/dev/sgx_provision      # DCAP provisioning
/var/run/aesmd/aesm.socket  # quote generation
```

The module is enabled automatically for any environment that declares a
`critical`-tier device (see `iac/README.md`, Section 2).

---

## 6. Host prerequisites

- SGX-capable CPU with **Flexible Launch Control (FLC)**.
- SGX driver / in-kernel SGX (`/dev/sgx_enclave`, `/dev/sgx_provision`).
- Intel **AESM** service running on the host for DCAP quote generation.
- DCAP PCCS reachable for collateral (or a caching PCCS in the network).

---

## 7. Relationship to the paper

Section IV.A (Layer 1 — Hardware Root of Trust) of the paper describes SGX
enclaves via Gramine as the higher protection tier assigned by IaC. This
directory is the concrete realization of that tier for the Vault initializer:
the `critical` sensitivity label in Terraform selects the SGX-shielded
initializer described here.
