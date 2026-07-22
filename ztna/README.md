# ZTNA — Twingate Connector (Layer 3 / Network Enforcement)

![app-tpm](https://img.shields.io/badge/project-app--tpm-blue)
![Twingate](https://img.shields.io/badge/Twingate-Connector-6C47FF)
![Docker](https://img.shields.io/badge/docker-compose-blue?logo=docker)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform)
![License](https://img.shields.io/badge/license-MIT-green)

> Component of the prototype described in:
> **"A Hybrid Zero Trust Architecture for Non-Interactive Authentication"**
> Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. — PPGIa/PUCPR, Brazil.

This module implements **Layer 3 (network enforcement / ZTNA)** of the `app-tpm` hybrid Zero Trust architecture, using **Twingate** in **on-premises Connector via Docker** mode. The goal is to publish the internal resources (the **Vault** from the `vault-tpm` project and the **IoT server** from the `iot-tpm` project) without exposing any inbound port, enforcing identity-based access instead of a VPN.

> This directory replaces the former PoC based on OpenZiti + Keycloak. The threat model and the role in the architecture remain the same (neutralize lateral movement, T1021); only the ZTNA technology changed to Twingate.

---

## 1. Why Twingate (on-premises Connector)

- **No inbound ports:** the Connector makes outbound-only connections to the
  Twingate Relay. No port needs to be opened in the PPGIA96 firewall.
- **Identity-based access:** users/devices authenticate to Twingate; the
  Connector only forwards traffic to Resources authorized by policy.
- **Complements TOTP + TPM:** even if a TOTP credential leaks, it cannot be used
  outside the network context enforced by the ZTNA.

---

## 2. Two-server topology

```
                         Twingate Cloud (Controller + Relays)
                                       ▲  (outbound only)
                                       │
┌──────────────────────────────────────────────────────────┐
│  PPGIA96  (production)                                     │
│                                                            │
│   ┌────────────────┐   ┌───────────────┐   ┌───────────┐  │
│   │ Vault          │   │ IoT Server    │   │ Twingate  │  │
│   │ (vault-tpm)    │◄──┤ (iot-tpm)     │   │ Connector │  │
│   │ :8200          │   │ REST :5000 /  │   │ (docker)  │  │
│   │ TOTP seeds     │   │ MQTT :8883    │   │  ztna/    │  │
│   └────────────────┘   └───────────────┘   └───────────┘  │
│         ▲ reads seed per device_id              │         │
│         └─────────────────────────────────────► publishes │
│                                                 Resources  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  PPGIA95  (testing / validation)                           │
│                                                            │
│   ┌──────────────────────┐   ┌──────────────────────────┐ │
│   │ Security tests       │   │ IoT client/server         │ │
│   │ (pentest/)           │   │ for validation (iot-tpm)  │ │
│   └──────────────────────┘   └──────────────────────────┘ │
│   Accesses the PPGIA96 resources through Twingate.        │
└──────────────────────────────────────────────────────────┘
```

| Server | Role | Components |
|---|---|---|
| **PPGIA96** | Production | Vault (`vault-tpm`, `:8200`), IoT server (`iot-tpm`, REST `:5000` / MQTT `:8883`), **Twingate Connector** (this directory) |
| **PPGIA95** | Testing / validation | Security tests (`pentest/`) and IoT client/server for validation (`iot-tpm`), accessing the PPGIA96 resources via Twingate |

---

## 3. Connector deployment (PPGIA96)

### 3.1 Generate the tokens in the Admin Console

1. Sign in to `https://<your-networkname>.twingate.com` as an administrator.
2. **Network → Connectors → Deploy Connector**.
3. Choose **On-premises → Docker**. The Console generates a token pair
   (`ACCESS_TOKEN` and `REFRESH_TOKEN`) shown **only once**.

### 3.2 Bring up the Connector

```bash
cd app-tpm/ztna/
cp .env.example .env
#  edit .env: TWINGATE_NETWORK, TWINGATE_ACCESS_TOKEN, TWINGATE_REFRESH_TOKEN
docker compose up -d
```

Check the status:

```bash
docker compose logs -f twingate-connector      # should show "Connected"
docker exec twingate-connector-ppgia96 ./connectord --version
```

In the Admin Console, the Connector shows up as **Online**.

> The `.env` file holds secrets and is **not versioned** (see the root
> `.gitignore`). Only `.env.example` is kept in the repository.

### 3.3 Compose details

- **Image:** `twingate/connector:1` (stable channel, automatic patch updates).
- **`sysctl net.ipv4.ping_group_range=0 2147483647`:** lets the Connector
  measure latency (ICMP) to the internal Resources.
- **`restart: unless-stopped` + `pull_policy: always`:** resilient restart and
  always up-to-date image when the container is recreated.
- **Watchtower label:** enables automatic updates if a Watchtower instance is
  running on the host.

---

## 4. Publish the internal Resources

In the Admin Console (**Resources → Add Resource**), point to the PPGIA96
services using the Connector from this directory. Suggested Resources:

| Resource | Internal address (from the Connector) | Use |
|---|---|---|
| Vault (vault-tpm) | `http://127.0.0.1:8200` or the PPGIA96 internal IP | Read/write of TOTP seeds by `device_id` |
| IoT Server REST | `http://127.0.0.1:5000` | `POST /login`, `POST /verify` |
| IoT Server MQTT | `mqtt://127.0.0.1:8883` | TOTP publish/verify |

Then create a **Group** and a **Policy** granting these Resources only to
authorized users/devices (for example, PPGIA95 and the administration
workstations). No other traffic reaches PPGIA96.

### 4.1 Example: IoT server Resource + Policy granting PPGIA95

The goal is: **only PPGIA95** (and administrators) may reach the PPGIA96 IoT
server; any other source is blocked.

#### Through the Admin Console UI

1. **Group** — create the `ppgia95-validation` group and associate with it the
   user/service running the IoT client on PPGIA95 (**Team → Groups → Add Group**).
2. **Resource** — **Resources → Add Resource**:
   - **Address:** `10.0.0.96` (PPGIA96 internal IP) or an internal alias, e.g.
     `iot.ppgia96.local`.
   - **Connector:** the Connector from this directory (`twingate-connector-ppgia96`).
   - **Restrict ports (recommended):** `TCP 5000` (REST) and/or `TCP 8883` (MQTT).
     This way, even when authorized, PPGIA95 only reaches the IoT service ports —
     the Vault (`:8200`) stays in a separate Resource, granted to admins only.
3. **Policy / Access** — on the Resource's **Access** tab, add the
   `ppgia95-validation` group. Set the **Security Policy** to require MFA and,
   optionally, device posture checks. Without belonging to that group, no host
   can even see the Resource.

#### Declarative via Terraform (consistent with the project's IaC approach)

```hcl
terraform {
  required_providers {
    twingate = {
      source  = "Twingate/twingate"
      version = "~> 3.0"
    }
  }
}

provider "twingate" {
  network    = "your-networkname"         # TWINGATE_NETWORK
  api_token  = var.twingate_api_token     # Admin Console API token
}

# On-premises Connector running on PPGIA96 (this directory).
data "twingate_remote_network" "ppgia96" {
  name = "ppgia96"
}

# Group representing the PPGIA95 validation server.
resource "twingate_group" "ppgia95_validation" {
  name = "ppgia95-validation"
}

# Resource: PPGIA96 IoT server, restricted to the REST/MQTT ports.
resource "twingate_resource" "iot_ppgia96" {
  name              = "IoT Server (PPGIA96)"
  address           = "10.0.0.96"                       # PPGIA96 internal IP
  remote_network_id = data.twingate_remote_network.ppgia96.id

  protocols = {
    allow_icmp = true
    tcp = {
      policy = "RESTRICTED"
      ports  = ["5000", "8883"]                          # REST and MQTT
    }
    udp = { policy = "DENY_ALL" }
  }

  # Access policy: only the PPGIA95 group, with mandatory MFA.
  access_group {
    group_id           = twingate_group.ppgia95_validation.id
    security_policy_id = data.twingate_security_policy.mfa.id

    # Periodic re-authorization (relogin) of the PPGIA95 access.
    access_policy {
      mode     = "AUTO_LOCK"
      duration = "7d"
    }
  }
}

# Predefined Security Policy in the Admin Console that requires MFA.
data "twingate_security_policy" "mfa" {
  name = "Require MFA"
}
```

> **Least-privilege principle:** publish the **Vault** (`:8200`) as a
> **separate** Resource, associated only with an administrators group — never
> with `ppgia95-validation`. PPGIA95 only needs to talk to the IoT server;
> direct Vault access must not be granted to the testing environment.

### 4.2 Required API token and running Terraform

#### Generate the API token

The `Twingate/twingate` provider authenticates with an **API token** (distinct
from the Connector tokens). To generate it:

1. In the Admin Console, go to **Settings → API → Generate Token**.
2. Give it a descriptive name (e.g., `terraform-ppgia96`).
3. Select the **Read, Write & Provision** permission — required for Terraform
   to create Groups, Resources, and Policies.
4. Copy the token immediately: it is **not shown again** after you close the
   window.

> The API token grants administrative access to your Twingate network. Treat it
> as a secret (same level as the Vault root token): never version it and revoke
> it if it leaks.

#### Provide the token securely

Use a variable marked as `sensitive` and pass the value via an **environment
variable** (recommended) or a `terraform.tfvars` outside version control:

```hcl
# variables.tf
variable "twingate_api_token" {
  description = "Twingate API token (Read, Write & Provision)"
  type        = string
  sensitive   = true
}
```

```bash
# Option A (recommended): environment variable
export TF_VAR_twingate_api_token="<your-api-token>"
#   or, directly on the provider, via TWINGATE_API_TOKEN="<your-token>"

# Option B: terraform.tfvars (add it to .gitignore — NEVER version it)
cat > terraform.tfvars <<'EOF'
twingate_api_token = "<your-api-token>"
EOF
echo "terraform.tfvars" >> .gitignore
```

#### Run

```bash
cd ztna/terraform/          # where the .tf files above live
terraform init             # downloads the Twingate/twingate ~> 3.0 provider
terraform plan             # review: 2 to create (group + resource)
terraform apply            # applies after confirming with "yes"
```

#### Expected `terraform apply` output

```text
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # twingate_group.ppgia95_validation will be created
  + resource "twingate_group" "ppgia95_validation" {
      + id   = (known after apply)
      + name = "ppgia95-validation"
    }

  # twingate_resource.iot_ppgia96 will be created
  + resource "twingate_resource" "iot_ppgia96" {
      + address           = "10.0.0.96"
      + id                = (known after apply)
      + name              = "IoT Server (PPGIA96)"
      + remote_network_id  = "UmVtb3RlTmV0d29yazoxMjM0"
      + protocols          = {
          + allow_icmp = true
          + tcp        = {
              + policy = "RESTRICTED"
              + ports  = ["5000", "8883"]
            }
          + udp        = { + policy = "DENY_ALL" }
        }
      + access_group {
          + group_id           = (known after apply)
          + security_policy_id = "U2VjdXJpdHlQb2xpY3k6NTY3"
          + access_policy {
              + mode     = "AUTO_LOCK"
              + duration = "7d"
            }
        }
    }

Plan: 2 to add, 0 to change, 0 to destroy.

Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes

twingate_group.ppgia95_validation: Creating...
twingate_group.ppgia95_validation: Creation complete after 1s [id=R3JvdXA6ODkw]
twingate_resource.iot_ppgia96: Creating...
twingate_resource.iot_ppgia96: Creation complete after 2s [id=UmVzb3VyY2U6MzQwNDQ3]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

The `id` values are opaque Base64 (a Twingate Admin API convention) and are used
for `terraform import` or cross-reference. After the apply, the **IoT Server
(PPGIA96)** Resource appears in the Admin Console associated with the
`ppgia95-validation` group, and only that group's members (with MFA) can reach
the IoT server.

> To also publish the Vault as an admin-restricted Resource, replicate the
> `twingate_resource` block pointing to `:8200` and associate it with an admins
> group — per the least-privilege note above.

---

## 5. How this fits into the IoT-TPM flow

1. The IoT device is provisioned by `iot-tpm/.../scripts/init_device.sh`: a
   **random TOTP seed** is generated, **sealed in the device's TPM**, and
   **registered in the PPGIA96 Vault** (by `device_id`).
2. The IoT server (PPGIA96) reads the seed from Vault and validates the TOTP.
3. All communication between the client (PPGIA95) and the server (PPGIA96)
   travels **through Twingate**: without the granted ZTNA access, the IoT
   server endpoints and the Vault are unreachable.

See the [`iot-tpm/`](../iot-tpm/README.md) and
[`vault-tpm/`](../vault-tpm/README.md) READMEs for the provisioning and
secret-management details.

---

## 6. References

- Twingate — Deploy Connector via Docker:
  <https://www.twingate.com/docs/docker>
- Twingate — Connectors (overview):
  <https://www.twingate.com/docs/connectors>
