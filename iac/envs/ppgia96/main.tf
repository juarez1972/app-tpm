###############################################################################
# Environment: ppgia96 (production)
#
# Wires every module together for the production network. The `devices` map
# assigns a sensitivity tier per device; the tier drives the hardware protection
# level (standard = TPM, high = TPM+SGX, critical = vTPM+TDX / SGX-shielded
# initializer). The SGX node is provisioned only when a critical device exists.
###############################################################################

terraform {
  # Use an encrypted remote backend in production so device seeds in state are
  # not stored in cleartext. Configure via `terraform init -backend-config=...`.
  backend "local" {
    path = "terraform.tfstate"
  }
}

# ── Providers ────────────────────────────────────────────────────────────────
provider "vault" {
  # VAULT_ADDR / VAULT_TOKEN (or AppRole) supplied via environment variables.
  # The token is scoped to app-policy; the root token stays TPM-sealed.
}

provider "docker" {}

provider "twingate" {
  # TWINGATE_API_TOKEN and TWINGATE_NETWORK supplied via environment variables.
}

# ── Inputs ───────────────────────────────────────────────────────────────────
variable "devices" {
  type = map(object({
    seed = optional(string)
    tier = optional(string, "standard")
  }))
  default = {
    "device-001" = { tier = "standard" } # TPM only
    "device-002" = { tier = "high" }     # TPM + SGX
    "gateway-01" = { tier = "critical" } # SGX-shielded initializer + TDX
  }
}

locals {
  has_critical = length([for id, d in var.devices : id if try(d.tier, "standard") == "critical"]) > 0
}

# ── Modules ──────────────────────────────────────────────────────────────────
module "vault" {
  source = "../../modules/vault-tpm"
}

module "devices" {
  source          = "../../modules/iot-devices"
  kv_mount        = module.vault.kv_mount
  device_base     = module.vault.device_base
  devices         = var.devices
  run_tpm_sealing = false # sealing runs on the device host, not from CI
}

module "compose" {
  source   = "../../modules/compose-stack"
  otp_mode = "hmac"
}

module "ztna" {
  source              = "../../modules/ztna"
  remote_network_name = "ppgia96"
}

module "sgx" {
  source       = "../../modules/sgx-node"
  enabled      = local.has_critical
  network_name = module.compose.network
}

# ── Outputs ──────────────────────────────────────────────────────────────────
output "device_tiers" {
  value = module.devices.device_tiers
}

output "otp_mode" {
  value = module.compose.otp_mode
}

output "sgx_enabled" {
  value = module.sgx.enabled
}

output "published_resources" {
  value = module.ztna.published_resources
}
