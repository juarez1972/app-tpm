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
6. [Deployment Topology (PPGIA96 / PPGIA95)](#6-deployment-topology-ppgia96--ppgia95)
7. [Prototype Modules](#7-prototype-modules)
   - [7.1 Vault + TPM Auto-Unseal (vault-tpm/)](#71-vault--tpm-auto-unseal-vault-tpm)
   - [7.2 IoT Agent with TPM + TOTP (iot-tpm/)](#72-iot-agent-with-tpm--totp-iot-tpm)
   - [7.3 ZTNA with Twingate Connector (ztna/)](#73-ztna-with-twingate-connector-ztna)
   - [7.4 Security & Performance Testing (pentest/)](#74-security--performance-testing-pentest)
8. [Logical Architecture of the nIA Flow](#8-logical-architecture-of-the-nia-flow)
9. [Experimental Results](#9-experimental-results)
10. [Roadmap](#10-roadmap)
11. [References](#11-references)
12. [License](#12-license)
13. [Authors](#13-authors)

---

## 1. Architecture Overview

The architecture rests on the premise that software-only security is insufficient for Non-Interactive Authentication (nIA) environments. By anchoring the HashiCorp Vault master key inside a **TPM 2.0** and delegating HMAC computation to hardware, cryptographic keys **never leave the silicon**, even under full operating-system compromise (MITRE ATT&CK T1003).

The network layer implements **ZTNA** via a **Twingate Connector** (deployed on-premises with Docker) so that TOTP credentials cannot be reused outside their strict network context, neutralizing lateral movement (T1021).

**Measured overhead:** ~75 ms per complete nIA transaction; **Vault RTO** reduced from ~3 minutes (manual unseal) to ~300 ms (TPM auto-unseal).

## 2. Security Pillars

### Hardware Protection (TPM 2.0 / SGX / TDX)

| Layer | Technology | Protection Provided |
|---|---|---|
| Baseline servers | TPM 2.0 (dTPM/fTPM) | Boot integrity (PCRs), Vault auto-unseal, TOTP via tpm2-pytss |
| Critical servers | Intel SGX + Gramine | Enclave isolation; CPU-encrypted memory (MEE) |
| Confidential cloud | Intel TDX + vTPM | Full Trust Domain; hypervisor cannot access VM RAM |
| IoT / Edge | TPM 2.0 (Infineon SLB9670 / swtpm) | Non-exportable HMAC seed sealed in the TPM (time-based TOTP) |

- **Root of Trust:** keys generated and stored inside the TPM with `fixedtpm` and `fixedparent` attributes.
- **Sealing:** the Vault unseal key is sealed against PCRs (0, 7), ensuring access only when firmware has not been tampered with.
- **TOTP seed sequestration:** the shared secret is a *Restricted Keyed-Hash* in TPM NVRAM — rollback is physically impossible.

### Secret Management (HashiCorp Vault)

- **Auto-unseal via PKCS#11 → TPM:** eliminates human intervention at boot time.
- **Dynamic credentials (short TTL):** Vault issues short-lived tokens for databases and APIs via IaC policies.
- **Lifecycle:** `Generated (plaintext in Vault)` → `Obfuscated (TOTP keystream in transit)` → `Discarded`.

### Zero Trust Connectivity (ZTNA)

- **Invisible network:** a Twingate Connector makes only outbound connections — no inbound ports are opened on the production server.
- **Continuous posture validation:** the ZTNA layer verifies identity, device health, and location before the TOTP request ever reaches the IoT server.
- **Micro-segmentation:** invalidates sessions on context change (IP, device), blocking pivoting.

### Hardware-Anchored TOTP Authentication

The nIA agent uses `tpm2-pytss` to request HMAC computation from the TPM without ever exposing the key:

```python
# TOTP computation delegated to hardware (Layer 2, Article Section V)
import time
from tpm2_pytss import ESAPI

def generate_hardware_totp(time_step, key_handle):
    ctx = ESAPI()
    T = int(time.time() // time_step)   # time counter (T0=0, step=30/60 s)
    hmac_result = ctx.hmac(key_handle, T)
    return truncate_to_totp(hmac_result) # key never leaves the chip
```

```
TOTP(K, T) = Truncate(HMAC-SHA-1_TPM(K, T)),  T = floor((now - T0) / X)
```

## 3. Repository Structure

```
app-tpm/
├── vault-tpm/          # Vault + auto-unseal via TPM (Layer 1 + 2)
│   ├── vault-init/         # Initializer: encrypts unseal keys with TPM
│   ├── tpm-validator/      # Health check: TPM, .enc files, and Vault
│   ├── tpm-data/           # Sealed unseal keys and root token (.enc)
│   ├── scripts/
│   │   └── setup_vault_policies.hcl  # Vault access policies
│   ├── docker-compose.yml
│   ├── system_status.sh
│   ├── test_tpm_integration.sh
│   └── README.md            # TPM-validated auto-unseal guide
│
├── iot-tpm/            # nIA agent for IoT: random TOTP seed sealed in TPM (Layer 1)
│   ├── README.md            # provisioning, TOTP over REST/MQTT, troubleshooting
│   ├── client-iot/
│   │   ├── client_rest_api/          # REST client + pyotp + TPM
│   │   │   ├── app/certs/gerar_certificados.py
│   │   │   ├── scripts/init_device.sh   # generate seed → seal in TPM → register in Vault
│   │   │   ├── client_iot.py            # recovers the seed from the TPM at runtime
│   │   │   ├── Dockerfile / Dockerfile.arm64
│   │   │   ├── docker-compose.yml
│   │   │   ├── .env.example
│   │   │   └── requirements.txt
│   │   └── client_mqtt/              # MQTT client for low-bandwidth IoT
│   │       ├── scripts/init_device.sh
│   │       ├── client_mqtt.py
│   │       ├── Dockerfile / Dockerfile.arm64
│   │       ├── docker-compose.yml
│   │       ├── .env.example
│   │       └── requirements.txt
│   └── server/
│       ├── gerar_certificados.py
│       ├── server_rest_api/          # FastAPI /login + /verify (reads seed from Vault)
│       │   ├── server_rest_api.py
│       │   ├── Dockerfile
│       │   ├── docker-compose.yml
│       │   ├── .env.example
│       │   └── requirements.txt
│       └── server_mqtt/              # MQTT subscriber (validates TOTP from Vault)
│           ├── server_mqtt.py
│           ├── mosquitto.conf
│           ├── Dockerfile
│           ├── docker-compose.yml
│           ├── .env.example
│           └── requirements.txt
│
├── ztna/               # ZTNA via Twingate Connector — on-premises Docker (Layer 3)
│   ├── docker-compose.yml   # twingate/connector:1
│   ├── .env.example         # TWINGATE_NETWORK / ACCESS / REFRESH tokens
│   └── README.md            # deploy + two-server topology (PPGIA96/PPGIA95)
│
├── pentest/            # Security and Performance Tests (Article Sections V, VI)
│   ├── README.md            # how to run both test families (English)
│   └── scripts/
│       ├── security/         # adversarial red-team (Nmap/OpenVAS/ZAP/SQLMap/Hydra + LLM)
│       │   ├── pentest.py                # orchestrator — Google Gemini (cloud), v1
│       │   ├── pentestv2.py              # orchestrator — Google Gemini (cloud), v2
│       │   ├── pentestv3.py              # orchestrator — Cyber-Llama/Ollama (local) + OpenVAS GMP
│       │   ├── start_scan_openvas.py     # trigger an OpenVAS/GVM scan (GMP over TLS)
│       │   ├── testa_conexao_openvas.py  # GVM connection/auth smoke-test
│       │   ├── teste_gemini.py           # Gemini connectivity smoke-test
│       │   └── users.txt / passwords.txt # Hydra brute-force dictionaries
│       └── performance/      # benchmarks & end-to-end latency tests
│           ├── bench_totp.py             # TOTP gen/verify + cached secret read (N=20k)
│           ├── rest_logic_test.py        # E2E REST with swtpm + Vault dev
│           ├── rest_nofvault_test.py     # E2E REST without Vault (TPM fallback)
│           ├── mqtt_nofvault_test.py     # E2E MQTT without broker/Vault
│           └── measurements_summary.md   # consolidated sandbox metrics
│
└── paper/             # Journal article (IEEEtran) + references + compiled PDF
    ├── hybrid_zt_nia.tex          # authoritative IEEEtran source
    ├── references.bib             # BibTeX bibliography (23 entries)
    ├── hybrid_zt_nia_preview.pdf  # compiled output (pdflatex + bibtex, 11 pages)
    └── build_preview.py           # legacy ReportLab preview generator
```

## 4. Technologies Used

| Category | Component | Version / Reference |
| --- | --- | --- |
| Hardware Root of Trust | TPM 2.0 (ISO/IEC 11889) | Infineon SLB9670/SLB9665 or swtpm |
| Confidential Computing | Intel SGX (Gramine/LibOS) | DCAP driver |
| Confidential VM | Intel TDX + vTPM | Sapphire Rapids+ |
| TPM SW Stack | tpm2-tss, tpm2-tools, tpm2-pytss | TCG-compliant |
| Secret Management | HashiCorp Vault (auto-unseal PKCS#11) | OSS |
| ZTNA | Twingate Connector (on-premises, Docker) | `twingate/connector:1` |
| nIA Authentication | TOTP (RFC 6238), HMAC (RFC 2104) | `pyotp` |
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

# Install dependencies for a specific module (e.g. the REST IoT client)
pip install -r iot-tpm/client-iot/client_rest_api/requirements.txt

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

#### Provision TOTP on TPM (Article sequence, Section VI.B)

```bash
# 1. Self-test and initialization
tpm2_selftest --full
tpm2_startup --clear

# 2. Create NV index for the sealed TOTP seed (time-based, RFC 6238)
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

## 6. Deployment Topology (PPGIA96 / PPGIA95)

The reference deployment uses **two virtual servers**. Production services run on
**PPGIA96**; **PPGIA95** is used for security testing and for running an IoT
instance for validation. All traffic between the two servers is mediated by the
**Twingate Connector** (ZTNA), so the production endpoints expose **no inbound
ports**.

```
                         Twingate Cloud (Controller + Relays)
                                       ▲  (outbound only)
                                       │
┌──────────────────────────────────────────────────────────┐
│  PPGIA96  (production)                                     │
│   ┌────────────────┐  ┌───────────────┐  ┌─────────────┐  │
│   │ Vault          │  │ IoT server    │  │ Twingate    │  │
│   │ (vault-tpm)    │◄─┤ (iot-tpm)     │  │ Connector   │  │
│   │ :8200          │  │ REST :5000 /  │  │ (docker)    │  │
│   │ TOTP seeds     │  │ MQTT :8883    │  │  ztna/      │  │
│   └────────────────┘  └───────────────┘  └─────────────┘  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  PPGIA95  (testing / validation)                          │
│   ┌──────────────────────┐  ┌──────────────────────────┐  │
│   │ Security testing     │  │ IoT client/server for     │  │
│   │ (pentest/)           │  │ validation (iot-tpm)      │  │
│   └──────────────────────┘  └──────────────────────────┘  │
│   Reaches PPGIA96 resources through Twingate (ZTNA).      │
└──────────────────────────────────────────────────────────┘
```

| Server | Role | Components |
|---|---|---|
| **PPGIA96** | Production | Vault (`vault-tpm`, `:8200`), IoT server (`iot-tpm`, REST `:5000` / MQTT `:8883`), Twingate Connector (`ztna/`) |
| **PPGIA95** | Testing / validation | Security testing (`pentest/`) and an IoT client/server for validation (`iot-tpm`), reaching PPGIA96 via Twingate |

## 7. Prototype Modules

### 7.1 Vault + TPM Auto-Unseal (vault-tpm/)

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

### 7.2 IoT Agent with TPM + TOTP (iot-tpm/)

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

### 7.3 ZTNA with Twingate Connector (ztna/)

Layer 3 (Network Enforcement) of the article, deployed as a **Twingate Connector
on-premises via Docker** (equivalent to *Deploy Connector → On-premises → Docker*
in the Twingate Admin Console). The Connector runs on **PPGIA96** and publishes
the Vault and the IoT server as Twingate Resources — no inbound ports are opened.

```bash
cd ztna

# 1. Generate the Connector tokens in the Twingate Admin Console:
#    Network → Connectors → Deploy Connector → On-premises → Docker

# 2. Configure .env with your network name and the tokens
cp .env.example .env
#    TWINGATE_NETWORK / TWINGATE_ACCESS_TOKEN / TWINGATE_REFRESH_TOKEN

# 3. Bring up the Connector
docker compose up -d
docker compose logs -f twingate-connector   # expect "Connected"
```

> **Dedicated README:** see [`ztna/README.md`](./ztna/README.md) for the full
> deploy procedure, the two-server topology, and how to publish the Vault and
> IoT server as Twingate Resources.

### 7.4 Security & Performance Testing (pentest/)

The `pentest/` module groups **all test scripts** used to evaluate the
architecture along two axes. Scripts live under `pentest/scripts/`, split into
`security/` and `performance/`. See [`pentest/README.md`](./pentest/README.md)
for the full instructions.

#### Security tests — `scripts/security/` (Article Section VI.A)

Autonomous red-team pipeline using local Llama 3.x (via Ollama) or Google
Gemini, integrating Nmap, OpenVAS/GVM, ZAPProxy, SQLMap and Hydra, with findings
mapped to MITRE ATT&CK.

```bash
cd pentest/scripts/security
pip install openai google-genai gvm-tools python-dotenv requests

# Configure credentials (config.env in this folder)
cat > config.env << 'EOF'
OPENVAS_IP=192.168.x.x
OPENVAS_USER=admin
OPENVAS_PASS=your_strong_password
# GEMINI_API_KEY=optional_key_for_cloud_mode
EOF
```

| Script | Description | LLM Model |
| --- | --- | --- |
| `pentest.py` | Orchestrator (cloud), v1 | Google Gemini 2.0 Flash |
| `pentestv2.py` | Orchestrator (cloud), v2 — flow checks | Google Gemini 2.0 Flash |
| `pentestv3.py` | Full on-premises + OpenVAS GMP | Cyber-Llama / Llama 3.x (Ollama) |
| `start_scan_openvas.py` | Trigger a single OpenVAS/GVM scan | — |
| `testa_conexao_openvas.py` / `teste_gemini.py` | Connectivity smoke-tests | — |

```bash
# Install Ollama and model (for the local, on-premises mode)
curl -fsSL https://ollama.com/install.sh | sh
ollama run llama3

# Run simulation (pentestv3 — local mode)
python pentestv3.py
```

#### Performance tests — `scripts/performance/`

Micro-benchmarks and end-to-end tests that measure TOTP generation/verification,
cached/Vault secret reads, TPM health-check, provisioning and hot-path latency.
Results feed the evaluation tables in the article and are consolidated in
[`pentest/scripts/performance/measurements_summary.md`](./pentest/scripts/performance/measurements_summary.md).

```bash
cd pentest/scripts/performance
pip install pyotp hvac

python3 bench_totp.py          # software-path micro-benchmark (no TPM/Vault needed)
python3 rest_nofvault_test.py  # E2E REST exercising the TPM (needs swtpm + tpm2-tools)
python3 mqtt_nofvault_test.py  # E2E MQTT via the real server handler
python3 rest_logic_test.py     # full E2E with a Vault dev server (needs the 'vault' binary)
```

> **Legal notice:** The security scripts are intended exclusively for
> **authorized security audits** and **academic research**. Use against targets
> without explicit permission is illegal. The authors accept no responsibility
> for misuse.

## 8. Logical Architecture of the nIA Flow

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
│                          │   TOTP = TPM_HMAC(K,T)│               │
│                          └──────────┬──────────┘                │
│                                     │ Obfuscated Payload         │
│  ┌──────────────────────────────────▼──────────────────────────┐│
│  │              ZTNA Gateway (Twingate Connector)              ││
│  │   Validates: identity + posture + location + TOTP           ││
│  └──────────────────────────────────┬───────────────────────────┘│
│                                     │ TLS Tunnel + ZTNA          │
│                          ┌──────────▼──────────┐                │
│                          │   Hub Services       │                │
│                          │   (GLPI, MariaDB,    │                │
│                          │    Nginx, NAS)        │                │
│                          └─────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘

Credential lifecycle:
  Generated (plaintext in Vault) → Obfuscated (TOTP in transit) → Discarded
```

**Boot and authentication flow:**

1. **Boot:** TPM validates firmware integrity via PCRs.
2. **Unseal:** Vault requests unseal key from TPM via PKCS#11 (~300 ms).
3. **Auth:** nIA agent generates TOTP via TPM and authenticates to the ZTNA Gateway.
4. **ZTNA verification:** device posture + TOTP validated simultaneously.
5. **Transaction:** credential travels obfuscated over TLS + ZTNA tunnel; only Hub Services de-obfuscates it.

## 9. Experimental Results

Full evaluation details are available in Section VI of the article.

### Performance (1,000 concurrent nIA requests — Ubuntu 22.04 LTS)

| Operation | Software-only | TPM (Tier 1) | SGX (Tier 2) | TDX (Tier 3) |
| --- | --- | --- | --- | --- |
| TOTP generation | ~2 ms | ~65 ms | ~85 ms | ~70 ms |
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

## 10. Roadmap

* [ ] **Post-Quantum TPM:** Evaluate CRYSTALS-Dilithium and SPHINCS+ in TPM 2.0 NV indices for long-lifecycle IoT deployments.
* [ ] **Federated LLM Red-Team:** Distribute adversarial simulation across multiple local models for consensus-based detection.
* [ ] **TDX Cross-Cloud Attestation:** Standardize vTPM attestation across AWS NitroTPM, Azure vTPM, and GCP vTPM.
* [ ] **Full Terraform integration:** IaC module with `standard | high | critical` labels for automatic protection-tier selection.

## 11. References

The full bibliography of the reference article is maintained as a BibTeX file at
[`paper/references.bib`](./paper/references.bib) (23 entries). The authoritative
article source is [`paper/hybrid_zt_nia.tex`](./paper/hybrid_zt_nia.tex); a
rendered preview is available at
[`paper/hybrid_zt_nia_preview.pdf`](./paper/hybrid_zt_nia_preview.pdf).

To compile the article with the external bibliography (IEEEtran + BibTeX),
replace the embedded `thebibliography` block in the `.tex` with:

```latex
\bibliographystyle{IEEEtran}
\bibliography{references}
```

then run: `pdflatex → bibtex → pdflatex → pdflatex`.

**Selected key references:**

- J. Oliveira, A. O. Santin, E. K. Viegas, and P. Horchulhack, "A non-interactive one-time password-based method to enhance the Vault security," in *AINA 2024*, LNDECT vol. 202, Springer, 2024, pp. 201–213. `oliveira2024`
- S. Rose, O. Borchert, S. Mitchell, and S. Connelly, "Zero trust architecture," NIST SP 800-207, 2020. [DOI](https://doi.org/10.6028/NIST.SP.800-207) `nist800207`
- Trusted Computing Group, "TPM 2.0 library specification, parts 1–4," Rev. 1.59, 2019. `tcg2019`
- D. M'Raihi et al., "TOTP: Time-based one-time password algorithm," IETF RFC 6238, 2011. `rfc6238`
- L. Coppolino et al., "An experimental evaluation of TEE technology evolution: SGX, SEV, and TDX," *Computers & Security*, 2025. [DOI](https://doi.org/10.1016/j.cose.2025.104457) `coppolino2025`

See `paper/references.bib` for the complete list (HOTP/RFC 4226, MITRE ATT&CK,
HashiCorp Vault auto-unseal, Shamir secret sharing, Intel SGX/TDX, ZTNA, and the
LLM red-teaming literature).

## 12. License

This project is licensed under the [MIT License](./LICENSE).

## 13. Authors

Developed by researchers from the Graduate Program in Computer Science (PPGIa) — PUCPR, Brazil.

| Name | E-mail |
| --- | --- |
| Juarez de Oliveira, M.Sc. | [juarez.oliveira@ppgia.pucpr.edu.br](mailto:juarez.oliveira@ppgia.pucpr.edu.br) |
| Juliano Sartori Langaro, M.Sc. | [juliano.langaro@ppgia.pucpr.edu.br](mailto:juliano.langaro@ppgia.pucpr.edu.br) |
| Fellipe Medeiros Veiga  , M.Sc. | [fellipe.veiga@ppgia.pucpr.edu.br](mailto:fellipe.veiga@ppgia.pucpr.edu.br) |
| Eduardo Kugler Viegas, PhD. *(Supervisor)* | [eduardo.viegas@ppgia.pucpr.br](mailto:eduardo.viegas@pucpr.br) |
| Altair Olivo Santin, PhD. *(Supervisor)* | [altair.santin@ppgia.pucpr.br](mailto:altair.santin@pucpr.br) |
 

Partially funded by CNPq — grants no. 307706/2025-7 and 407879/2023-4.
