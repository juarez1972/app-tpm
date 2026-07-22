###############################################################################
# Environment: ppgia95 (validation / staging)
#
# Mirrors production but with a reduced device set and no critical tier, so the
# SGX node is not provisioned. Useful for exercising the HMAC envelope and the
# Vault/ZTNA wiring before promoting to ppgia96.
###############################################################################

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "vault" {}
provider "docker" {}
provider "twingate" {}

variable "devices" {
  type = map(object({
    seed = optional(string)
    tier = optional(string, "standard")
  }))
  default = {
    "lab-device-001" = { tier = "standard" }
    "lab-device-002" = { tier = "high" }
  }
}

locals {
  has_critical = length([for id, d in var.devices : id if try(d.tier, "standard") == "critical"]) > 0
}

module "vault" {
  source = "../../modules/vault-tpm"
}

module "devices" {
  source          = "../../modules/iot-devices"
  kv_mount        = module.vault.kv_mount
  device_base     = module.vault.device_base
  devices         = var.devices
  run_tpm_sealing = false
}

module "compose" {
  source   = "../../modules/compose-stack"
  otp_mode = "hmac"
}

module "ztna" {
  source              = "../../modules/ztna"
  remote_network_name = "ppgia95"
}

module "sgx" {
  source       = "../../modules/sgx-node"
  enabled      = local.has_critical # false in this env
  network_name = module.compose.network
}

output "device_tiers" {
  value = module.devices.device_tiers
}

output "otp_mode" {
  value = module.compose.otp_mode
}

output "sgx_enabled" {
  value = module.sgx.enabled
}
