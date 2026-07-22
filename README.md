# Hybrid Zero Trust Architecture for Non-Interactive Authentication

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![TPM](https://img.shields.io/badge/hardware-TPM%202.0-orange)
![Docker](https://img.shields.io/badge/docker-compose-blue)

> **Reference Article:** "A Hybrid Zero Trust Architecture for Non-Interactive Authentication: Integrating Hardware Trust Anchors with Software-Defined Secret Management in Infrastructure as Code"
> Oliveira, J., Langaro, J. S.; Veiga, F. M.;  Viegas, E. K.; Santin, A. O.; — PPGIa/PUCPR, Brazil.

This repository contains the reference implementation of the hybrid architecture proposed in the article above. The prototype integrates **hardware trust anchors** (TPM 2.0, Intel SGX, Intel TDX) with **software-defined secret management** (HashiCorp Vault) and **network micro-segmentation** (Zero Trust Network Access — ZTNA), eliminating the "Secret Zero" problem in Infrastructure as Code (IaC) and IoT environments.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Security Pillars](#2-security-pillars)
3. [Repository Structure](#3-repository-structure)
4. [Technologies Used](#4-technologies-used)
5. [Setup and Installation](#5-setup-and-installation)
   - [5.1 General prerequisites](#51-general-prerequisites)
   - [5.2 TPM support on Linux host](#52-tpm-support-on-linux-host)
   - [5.3 SGX support on Linux host](#53-sgx-support-on-linux-host)
   - [5.4 TDX support on Linux host](#54-tdx-support-on-linux-host)
6. [Prototype Modules](#6-prototype-modules)
   - [6.1 HOTP/HMAC (hotp/)](#61-hotphmac-hotp)
   - [6.2 Vault + TPM Auto-Unseal (vault-tpm/)](#62-vault--tpm-auto-unseal-vault-tpm)
   - [6.3 IoT Client with TPM (iot-tpm/)](#63-iot-client-with-tpm-iot-tpm)
   - [6.4 ZTNA with OpenZiti and Keycloak (ztna/)](#64-ztna-with-openziti-and-keycloak-ztna)
   - [6.5 Web Proxy (proxy-web/)](#65-web-proxy-proxy-web)
   - [6.6 Adversarial Simulation with LLM (pentest/)](#66-adversarial-simulation-with-llm-pentest)
7. [Logical Architecture of the nIA Flow](#7-logical-architecture-of-the-nia-flow)
8. [Experimental Results](#8-experimental-results)
9. [Roadmap](#9-roadmap)
10. [License](#10-license)
11. [Authors](#11-authors)

---

## 1. Architecture Overview

The architecture rests on the premise that software-only security is insufficient for Non-Interactive Authentication (nIA) environments. By anchoring the HashiCorp Vault master key inside a **TPM 2.0** and delegating HMAC computation to hardware, cryptographic keys **never leave the silicon**, even under full operating-system compromise (MITRE ATT&CK T1003).

The network layer implements **ZTNA** via OpenZiti or Twingate so that HOTP-obfuscated credentials cannot be reused outside their strict context, neutralizing lateral movement (T1021).

**Measured overhead:** ~75 ms per complete nIA transaction; **Vault RTO** reduced from ~3 minutes (manual unseal) to ~300 ms (TPM auto-unseal).

## 2. Security Pillars

### Hardware Protection (TPM 2.0 / SGX / TDX)

| Layer | Technology | Protection Provided |
|---|---|---|
| Baseline servers | TPM 2.0 (dTPM/fTPM) | Boot integrity (PCRs), Vault auto-unseal, HOTP via tpm2-pytss |
| Critical servers | Intel SGX + Gramine | Enclave isolation; CPU-encrypted memory (MEE) |
| Confidential cloud | Intel TDX + vTPM | Full Trust Domain; hypervisor cannot access VM RAM |
| IoT / Edge | TPM 2.0 (Infineon SLB9670 / swtpm) | Non-exportable HMAC seed; monotonic counter in NVRAM |

- **Root of Trust:** keys generated and stored inside the TPM with `fixedtpm` and `fixedparent` attributes.
- **Sealing:** the Vault unseal key is sealed against PCRs (0, 7), ensuring access only when firmware has not been tampered with.
- **HOTP seed sequestration:** the shared secret is a *Restricted Keyed-Hash* in TPM NVRAM — rollback is physically impossible.

### Secret Management (HashiCorp Vault)

- **Auto-unseal via PKCS#11 → TPM:** eliminates human intervention at boot time.
- **Dynamic credentials (short TTL):** Vault issues short-lived tokens for databases and APIs via IaC policies.
- **Lifecycle:** `Generated (plaintext in Vault)` → `Obfuscated (HOTP keystream in transit)` → `Discarded`.

### Zero Trust Connectivity (ZTNA)

- **Invisible network:** OpenZiti (embedded SDK, no open ports) or Twingate (managed).
- **Continuous posture validation:** the ZTNA gateway verifies identity, device health, and location before accepting the HOTP.
- **Micro-segmentation:** invalidates sessions on context change (IP, device), blocking pivoting.

### Hardware-Anchored HOTP Authentication

The nIA agent uses `tpm2-pytss` to request HMAC computation from the TPM without ever exposing the key:

```python
# HOTP computation delegated to hardware (Layer 2, Article Section V)
from tpm2_pytss import ESAPI

def generate_hardware_hotp(nv_index, key_handle):
    ctx = ESAPI()
    ctx.nv_increment(nv_index)          # increment monotonic counter inside TPM
    counter_val = ctx.nv_read(nv_index)
    hmac_result = ctx.hmac(key_handle, counter_val)
    return truncate_to_hotp(hmac_result) # key never leaves the chip
```

```
HOTP(K, C) = Truncate(HMAC-SHA-1_TPM(K, C))
```

## 3. Repository Structure

```
app-tpm/
├── hotp/               # HOTP/TOTP client-server prototype (Layer 2)
│   ├── Client/         # Python client with pyotp
│   └── Server/         # FastAPI server with TOTP verification
│
├── vault-tpm/          # Vault + auto-unseal via TPM (Layer 1 + 2)
│   ├── vault-init/         # Initializer: encrypts unseal keys with TPM
│   ├── tpm-validator/      # Health check: TPM, .enc files, and Vault
│   ├── tpm-data/           # Sealed unseal keys and root token (.enc)
│   ├── scripts/
│   │   └── setup_vault_policies.hcl  # Vault access policies
│   ├── docker-compose.yml
│   ├── system_status.sh
│   └── test_tpm_integration.sh
│
├── iot-tpm/            # nIA agent for IoT with TPM verification (Layer 1)
│   ├── client-iot/
│   │   ├── client_rest_api/     # REST client + pyotp + TPM validation
│   │   │   ├── app/
│   │   │   │   └── certs/
│   │   │   │       └── gerar_certificados.py
│   │   │   ├── client_iot.py
│   │   │   └── requirements.txt
│   │   └── client_mqtt/         # MQTT client for low-bandwidth IoT
│   │       ├── Dockerfile
│   │       ├── Dockerfile.arm64
│   │       ├── client_mqtt.py
│   │       ├── docker-compose.yml
│   │       └── requirements.txt
│   ├── server/
│   │   ├── gerar_certificados.py
│   │   ├── server_rest_api/
│   │   │   ├── main.py
│   │   │   ├── server_rest_api.py
│   │   │   ├── docker-compose.yml
│   │   │   └── requirements.txt
│   │   └── server_mqtt/
│   │       ├── Dockerfile
│   │       ├── docker-compose.yml
│   │       ├── mosquitto.conf
│   │       ├── server_mqtt.py
│   │       └── requirements.txt
│   └── (per-protocol clients/servers, see iot-tpm/README.md)
│
├── ztna/               # ZTNA PoC with OpenZiti + Keycloak (Layer 3)
│   ├── docker-compose.yml
│   ├── check_poc.sh
│   ├── backup/              # Previous compose variants
│   └── openziti/
│       └── docker-compose-openziti.yml
│
├── proxy-web/          # Demo web proxy with dashboard
│
├── pentest/            # Adversarial simulation with LLM (Article Section VI.A)
│   ├── pentest.py      # Basic orchestrator (Nmap + OpenVAS)
│   ├── pentestv2.py    # Version with Google Gemini API
│   └── pentestv3.py    # Full version: local Cyber-Llama (Ollama)
│
└── web-app/            # Integrated demonstration application
```

> **Note on `hotp/antigos/`:** a `hotp/antigos/` subdirectory (containing earlier development iterations) is referenced in the article but could not be confirmed in the current API tree; it may have been removed or not yet pushed.

## 4. Technologies Used

| Category | Component | Version / Reference |
| --- | --- | --- |
| Hardware Root of Trust | TPM 2.0 (ISO/IEC 11889) | Infineon SLB9670/SLB9665 or swtpm |
| Confidential Computing | Intel SGX (Gramine/LibOS) | DCAP driver |
| Confidential VM | Intel TDX + vTPM | Sapphire Rapids+ |
| TPM SW Stack | tpm2-tss, tpm2-tools, tpm2-pytss | TCG-compliant |
| Secret Management | HashiCorp Vault (auto-unseal PKCS#11) | OSS |
| ZTNA | OpenZiti (Apache 2.0), Twingate, NetBird | — |
| IdP / MFA | Keycloak + Entra ID (OIDC/SAML) | — |
| nIA Authentication | HOTP (RFC 4226), HMAC (RFC 2104) | — |
| Infrastructure | Docker, Docker Compose, Terraform | — |
| Language | Python 3.10+, Shell Script | — |
| Adversarial Simulation | Llama 3.x via Ollama / Google Gemini | Section VI.A |

## 5. Setup and Installation

### 5.1 General prerequisites

* System with TPM 2.0 support (or `swtpm` simulator for CI/CD).
* Docker and Docker Compose installed.
* Python 3.10+ with virtual environment support.

```bash
# Clone the repository
git clone https://github.com/juarez1972/app-tpm.git
cd app-tpm

# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies for a specific module (e.g. hotp/Client)
pip install -r hotp/Client/requirements.txt

# To deactivate the virtual environment
deactivate
```

### 5.2 TPM support on Linux host

#### Verify TPM presence

```bash
# TPM device in sysfs
ls /sys/class/tpm/
# Expected: tpm0 or tpmrm0

# Character devices in /dev
ls /dev/tpm*
# Expected: /dev/tpm0 and/or /dev/tpmrm0

# Loaded TPM kernel modules
lsmod | grep tpm
# Expected: tpm_tis, tpm_tis_core, tpm, tpm_crb, etc.
```

#### Install TPM2 tools

```bash
sudo apt update
sudo apt install tpm2-tools

# Functional validation: should return random bytes
sudo tpm2_getrandom 4

# Display TPM capabilities and version
sudo tpm2_getcap properties-fixed | head
```

#### Provision HOTP on TPM (Article sequence, Section VI.B)

```bash
# 1. Self-test and initialization
tpm2_selftest --full
tpm2_startup --clear

# 2. Create NV index and monotonic counter
tpm2_nvdefine -C o -s 8 \
  -a "ownerread|ownerwrite|authread|authwrite|extend" \
  -p nvpass 0x1500016

# 3. Generate restricted HMAC key (never exportable)
tpm2_createprimary -C o -g sha256 -G hmac -c primary.ctx
tpm2_create -C primary.ctx -g sha256 -G hmac \
  -u hmac.pub -r hmac.priv \
  -a "restricted|sign|fixedtpm|fixedparent"

# 4. Seal Vault unseal key against PCRs (boot integrity)
tpm2_pcrread sha256:7
tpm2_createpolicy --policy-pcr -l sha256:0,7 -L policy.pcr
tpm2_create -C primary.ctx -i unseal.key \
  -L policy.pcr -r seal.priv -u seal.pub -c seal.ctx
```

> The `fixedtpm` and `fixedparent` attributes ensure the key **never leaves the chip**, even under full OS compromise.

### 5.3 SGX support on Linux host

The process involves three steps: verify hardware/BIOS support, install the driver/SDK/PSW, and run test samples.

#### 1. Prerequisites and verification

```bash
# Check SGX CPU flags
grep -m1 sgx /proc/cpuinfo
```

In BIOS/UEFI, enable SGX (*Enabled* or *Software Controlled* mode) and disable Secure Boot if the driver is not signed. Install matching kernel headers:

```bash
sudo apt install linux-headers-$(uname -r) build-essential dkms
```

#### 2. Install the DCAP driver

```bash
# Option 1: Download binary installer from Intel
wget https://download.01.org/intel-sgx/latest/linux-latest/distro/ubuntu22.04-server/sgx_linux_x64_driver_<version>.bin
chmod +x sgx_linux_x64_driver_<version>.bin && sudo ./sgx_linux_x64_driver_<version>.bin

# Option 2: Compile from source
git clone https://github.com/intel/linux-sgx-driver
cd linux-sgx-driver && make
sudo cp isgx.ko /lib/modules/$(uname -r)/kernel/drivers/intel/sgx/
sudo depmod && sudo modprobe isgx

# Verify activation
lsmod | grep sgx
ls /dev/sgx/enclave  # or /dev/isgx depending on driver version
```

#### 3. Install SDK and PSW

```bash
# Build dependencies
sudo apt install ocaml automake autoconf cmake python3 \
  libssl-dev libcurl4-openssl-dev libprotobuf-dev

# Download and install Intel SDK
wget https://download.01.org/intel-sgx/latest/linux-latest/distro/ubuntu22.04-server/sgx_linux_x64_sdk_<version>.bin
chmod +x sgx_linux_x64_sdk_<version>.bin
sudo ./sgx_linux_x64_sdk_<version>.bin --prefix /opt/intel
source /opt/intel/sgxsdk/environment

# Install PSW via Intel APT repository
echo "deb [arch=amd64] https://download.01.org/intel-sgx/sgx_repo/ubuntu $(lsb_release -sc) main" \
  | sudo tee /etc/apt/sources.list.d/intel-sgx.list
sudo apt update && sudo apt install libsgx-urts libsgx-launch libsgx-epid libsgx-quote-ex
```

#### 4. Test with SDK samples

```bash
cd /opt/intel/sgxsdk/SampleCode/SampleEnclave
make SGX_MODE=HW    # or SGX_MODE=SIM for environments without hardware
./app
```

> Confirm the AESM service is active: `systemctl status aesmd`

### 5.4 TDX support on Linux host

Requires Intel Xeon processors with TDX (Sapphire Rapids, Emerald Rapids, Xeon 6) and Ubuntu Server 24.04 LTS.

#### 1. Update the system

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

#### 2. Enable TDX in BIOS/UEFI

In the *CPU / Processor / Socket Configuration* section, enable:

| Option | Value |
| --- | --- |
| Memory Encryption (TME) | Enable |
| Total Memory Encryption Multi-Tenant (TME-MT) | Enable |
| TME-MT memory integrity | **Disable** |
| Trust Domain Extension (TDX) | Enable |
| TDX Secure Arbitration Mode Loader (SEAM Loader) | Enable |
| TME-MT/TDX key split | Non-zero value |
| SW Guard Extensions (SGX) | Enable |

#### 3. Enable TDX in the kernel

```bash
sudo nano /etc/default/grub
# Add to GRUB_CMDLINE_LINUX_DEFAULT:
# nohibernate kvm_intel.tdx=1

sudo update-grub && sudo reboot

# Verify after reboot
cat /proc/cmdline           # should contain: nohibernate kvm_intel.tdx=1
sudo dmesg | grep -i tdx    # should show: virt/tdx: module initialized
```

#### 4. Install the TDX virtualization stack

```bash
sudo apt install qemu-system-x86 ovmf-inteltdx libvirt-daemon-system libvirt-clients
ls -l /usr/share/ovmf/OVMF.inteltdx.ms.fd  # should exist with several MB
```

#### 5. Use the Canonical/TDX shortcut (recommended)

```bash
git clone -b noble-24.04 https://github.com/canonical/tdx.git
cd tdx

# Configure attestation (optional)
# TDX_SETUP_ATTESTATION=1  in the setup-tdx-config file

sudo ./setup-tdx-host.sh
sudo reboot

# Create TD guest image
cd tdx/guest-tools/image
sudo ./create-td-image.sh -v 24.04
# Generates: tdx-guest-ubuntu-24.04-*.qcow2
# Change the default password (123456) before using in production.
```

#### 6. Start a Trust Domain (TD) via QEMU

```bash
qemu-system-x86_64 \
  -accel kvm -smp 32 -m 16G -cpu host \
  -object '{"qom-type":"tdx-guest","id":"tdx","quote-generation-socket":{"type":"vsock","cid":"2","port":"4050"}}' \
  -object memory-backend-ram,id=mem0,size=16G \
  -machine q35,kernel_irqchip=split,confidential-guest-support=tdx,memory-backend=mem0 \
  -bios /usr/share/ovmf/OVMF.inteltdx.ms.fd \
  -nographic -nodefaults -vga none \
  -drive file=tdx-guest-ubuntu-24.04-generic.qcow2,if=none,id=virtio-disk0 \
  -device virtio-blk-pci,drive=virtio-disk0 \
  -serial stdio
```

#### 7. Verify TDX inside the guest

```bash
sudo dmesg | grep -i tdx
# Expected: "tdx: Guest detected"
ls -l /dev/tdx_guest   # should exist as a char device
```

## 6. Prototype Modules

### 6.1 HOTP/HMAC (hotp/)

Reference implementation of the HOTP/TOTP client-server pipeline (Layer 2 of the article).

```bash
cd hotp

# Start the server (FastAPI, port 5000)
python Server/server.py
# The GET /setup endpoint returns the dynamic OTP_SECRET for synchronization

# In another terminal, obtain the secret and configure the client
# Edit hotp/Client/client.py: OTP_SECRET = "<value from /setup>"
python Client/client.py
```

> **Security note:** In production, replace `FIXED_USER`, `FIXED_PASS`, and `OTP_SECRET` with environment variables. The article's HOTP is delegated to the TPM; the current server uses `pyotp` as a baseline for hardware-free testing.

**Flow:**

1. Client sends `POST /login` with credentials → receives `session_token`
2. Every 60 s: client generates TOTP and sends `POST /verify` with token + OTP
3. If OTP is invalid, the session is terminated immediately

### 6.2 Vault + TPM Auto-Unseal (vault-tpm/)

Implements the **Hardware Auto-Unseal** described in Section V of the article.

```bash
cd vault-tpm

# Bring up the full environment (Vault + TPM Initializer + Validator)
docker-compose up -d

# Check system status
./system_status.sh

# Test TPM ↔ Vault integration
./test_tpm_integration.sh
```

**Components:**

* `vault-init/vault_initializer.py`: encrypts unseal keys with a real or simulated TPM; saves `.enc` for production and `.txt` for debugging.
* `tpm-validator/tpm_validator.py`: periodic health check (TPM, `.enc` files, Vault) exposed on port 8080.
* `scripts/setup_vault_policies.hcl`: minimum-privilege access policies for services that interact with Vault.

> **Note:** In dev mode (`VAULT_DEV_ROOT_TOKEN_ID=root`), the default token is `root`. In production, remove dev mode and use TPM-only auto-unseal.

### 6.3 IoT Client with TPM (iot-tpm/)

nIA agent for IoT devices (Raspberry Pi 4/5, ARM64 Yocto) as described in Section VI.B of the article.

> **Dedicated README:** `iot-tpm/` has its own detailed documentation — see [`iot-tpm/README.md`](./iot-tpm/README.md) for full setup, multi-architecture build instructions, and security flow details.

```bash
# From the repository root, enter the iot-tpm module
cd iot-tpm/

# 1. Provision the device once: seal the TOTP secret in the TPM + register it in Vault
cd client-iot/client_rest_api/
DEVICE_ID=device-001 VAULT_ADDR=http://<server-ip>:8200 VAULT_TOKEN=<app_token> \
  ./scripts/init_device.sh

# 2. Start the REST API server (reads the secret from Vault by device_id)
cd ../../server/server_rest_api/
docker compose up --build -d

# 3. Run the REST client (unseals the secret from the TPM into RAM, TOTP loop)
cd ../../client-iot/client_rest_api/
pip install -r requirements.txt
DEVICE_ID=device-001 API_URL=http://<server-ip>:5000 python client_iot.py

# MQTT alternative (low-bandwidth IoT) — paths relative to iot-tpm/
pip install -r client-iot/client_mqtt/requirements.txt
python client-iot/client_mqtt/client_mqtt.py

# MQTT server (subscriber)
python server/server_mqtt/server_mqtt.py
```

> The IoT client verifies the TPM via `tpm2_getrandom` before authenticating. If the TPM is not operational, authentication is aborted — the expected behavior under the two-channel model (Section VI.D). The per-device TOTP secret is **sealed in the client's TPM** (provisioned by `scripts/init_device.sh`) and **registered in the server's Vault**; the client unseals it into RAM at startup and authenticates via time-based OTP over REST/MQTT.

### 6.4 ZTNA with OpenZiti and Keycloak (ztna/)

PoC for Layer 3 (Network Enforcement) of the article, validating the replacement of VPN with identity-based ZTNA.

```bash
cd ztna

# 1. Create shared network
docker network create ziti-shared-net

# 2. Configure .env (copy and adjust)
cp .env.example .env   # create if it does not exist
# Set: ZITI_PWD, ZITI_CTRL_EDGE_ADVERTISED_ADDRESS, etc.

# 3. Bring up layers in order
docker-compose -f backup/docker-compose-keycloak.yml up -d    # IdP
docker-compose -f openziti/docker-compose-openziti.yml up -d  # ZTNA

# 4. Access management consoles
# https://<ip>:8444  → ZAC (Ziti Admin Console)
# http://<ip>:8080   → Keycloak
```

**Auto-enrollment for scale:**

```bash
docker exec -it ziti-controller ziti edge create ext-jwt-signer "keycloak-ztna" \
  --claims-property "email" \
  --issuer "http://localhost:8080/realms/ziti-realm" \
  --jwks-endpoint "http://keycloak:8080/realms/ziti-realm/protocol/openid-connect/certs" \
  --external-id-claim "email" \
  --auto-enrollment-enabled
```

### 6.5 Web Proxy (proxy-web/)

Demonstration dashboard that aggregates status from all architecture components.

```bash
cd proxy-web
docker-compose up -d
# Access: http://localhost:<configured port>
./deploy.sh   # for zero-downtime updates
```

### 6.6 Adversarial Simulation with LLM (pentest/)

Autonomous red-team pipeline described in Section VI.A of the article, using local Llama 3.x (via Ollama) or Google Gemini.

```bash
cd pentest
pip install openai gvm-tools python-dotenv requests

# Set environment variables
cat > .env << 'EOF'
OPENVAS_IP=192.168.x.x
OPENVAS_USER=admin
OPENVAS_PASS=your_strong_password
# GEMINI_API_KEY=optional_key_for_cloud_mode
EOF
```

| Version | Description | LLM Model |
| --- | --- | --- |
| `pentest.py` | Basic: Nmap + OpenVAS | — |
| `pentestv2.py` | Cloud AI analysis | Google Gemini 2.0 Flash |
| `pentestv3.py` | Full on-premises (production) | Cyber-Llama / Llama 3.x (Ollama) |

```bash
# Install Ollama and model
curl -fsSL https://ollama.com/install.sh | sh
ollama run llama3

# Run simulation (pentestv3 — local mode)
python pentestv3.py
```

> **Legal notice:** This software is intended exclusively for **authorized security audits** and **academic research**. Use against targets without explicit permission is illegal. The authors accept no responsibility for misuse.

## 7. Logical Architecture of the nIA Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    IaC / IoT INFRASTRUCTURE                      │
│                                                                  │
│  ┌─────────────┐     ┌──────────────────────────────────────┐   │
│  │  TPM 2.0    │     │          HashiCorp Vault              │   │
│  │  (Layer 1)  │────▶│  Auto-Unseal via PKCS#11 ← TPM Key   │   │
│  │  SGX / TDX  │     │  Dynamic credentials (short TTL)      │   │
│  └─────────────┘     └──────────────┬───────────────────────┘   │
│                                     │                            │
│                          ┌──────────▼──────────┐                │
│                          │   nIA Agent          │                │
│                          │   (tpm2-pytss)       │                │
│                          │   HOTP = TPM_HMAC(K,C)│               │
│                          └──────────┬──────────┘                │
│                                     │ Obfuscated Payload         │
│  ┌──────────────────────────────────▼──────────────────────────┐│
│  │              ZTNA Gateway (OpenZiti / Twingate)              ││
│  │   Validates: identity + posture + location + HOTP           ││
│  └──────────────────────────────────┬───────────────────────────┘│
│                                     │ TLS Tunnel + ZTNA          │
│                          ┌──────────▼──────────┐                │
│                          │   Hub Services       │                │
│                          │   (GLPI, MariaDB,    │                │
│                          │    Nginx, NAS)        │                │
│                          └─────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘

Credential lifecycle:
  Generated (plaintext in Vault) → Obfuscated (HOTP in transit) → Discarded
```

**Boot and authentication flow:**

1. **Boot:** TPM validates firmware integrity via PCRs.
2. **Unseal:** Vault requests unseal key from TPM via PKCS#11 (~300 ms).
3. **Auth:** nIA agent generates HOTP via TPM and authenticates to the ZTNA Gateway.
4. **ZTNA verification:** device posture + HOTP validated simultaneously.
5. **Transaction:** credential travels obfuscated over TLS + ZTNA tunnel; only Hub Services de-obfuscates it.

## 8. Experimental Results

Full evaluation details are available in Section VI of the article.

### Performance (1,000 concurrent nIA requests — Ubuntu 22.04 LTS)

| Operation | Software-only | TPM (Tier 1) | SGX (Tier 2) | TDX (Tier 3) |
| --- | --- | --- | --- | --- |
| HOTP generation | ~2 ms | ~65 ms | ~85 ms | ~70 ms |
| Vault authentication | ~45 ms | ~110 ms | ~130 ms | ~115 ms |
| nIA end-to-end | ~120 ms | ~195 ms | ~225 ms | ~205 ms |
| Auto-unseal (RTO) | ~3 min | ~300 ms | ~350 ms | ~320 ms |

### Security (LLM Red-Team — 500 MITRE ATT&CK scenarios)

| MITRE Tactic | Technique | Software-only | Hybrid Architecture |
| --- | --- | --- | --- |
| TA0001 | T1078 Valid Accounts | 8% | **0%** |
| TA0004 | T1068 Privilege Escalation | 15% | **0%** |
| TA0006 | T1003 OS Credential Dumping | 22% | **0%** |
| TA0006 | T1552 Unsecured Credentials | 35% | **0%** |
| TA0008 | T1021 Remote Services | 12% | **0%** |

> Average bypass rate on pure software architecture: **18.4%**. On the hybrid architecture: **0%** across 500 scenarios.

## 9. Roadmap

* [ ] **Post-Quantum TPM:** Evaluate CRYSTALS-Dilithium and SPHINCS+ in TPM 2.0 NV indices for long-lifecycle IoT deployments.
* [ ] **Federated LLM Red-Team:** Distribute adversarial simulation across multiple local models for consensus-based detection.
* [ ] **TDX Cross-Cloud Attestation:** Standardize vTPM attestation across AWS NitroTPM, Azure vTPM, and GCP vTPM.
* [ ] **Full Terraform integration:** IaC module with `standard | high | critical` labels for automatic protection-tier selection.

## 10. License

This project is licensed under the [MIT License](./LICENSE).

## 11. Authors

Developed by researchers from the Graduate Program in Computer Science (PPGIa) — PUCPR, Brazil.

| Name | E-mail |
| --- | --- |
| Juarez de Oliveira, M.Sc. | [juarez.oliveira@ppgia.pucpr.edu.br](mailto:juarez.oliveira@ppgia.pucpr.edu.br) |
| Juliano Sartori Langaro, M.Sc. | [juliano.langaro@ppgia.pucpr.edu.br](mailto:juliano.langaro@ppgia.pucpr.edu.br) |
| Fellipe Medeiros Veiga  , M.Sc. | [fellipe.veiga@ppgia.pucpr.edu.br](mailto:fellipe.veiga@ppgia.pucpr.edu.br) |
| Eduardo Kugler Viegas, PhD. *(Supervisor)* | [eduardo.viegas@ppgia.pucpr.br](mailto:eduardo.viegas@pucpr.br) |
| Altair Olivo Santin, PhD. *(Supervisor)* | [altair.santin@ppgia.pucpr.br](mailto:altair.santin@pucpr.br) |
 

Partially funded by CNPq — grants no. 307706/2025-7 and 407879/2023-4.
