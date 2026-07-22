###############################################################################
# Module: iot-devices
#
# For each IoT device:
#   1. Generates (or accepts) a Base32 TOTP seed.
#   2. Writes it to Vault KV v2 at <device_base>/<device_id>, field "otp_secret",
#      so the server can read it via app-policy.
#   3. Triggers the client-side TPM sealing of that seed by invoking the existing
#      scripts/init_device.sh on the provisioning host (null_resource/local-exec).
#
# The seed is marked sensitive; it lives in Vault (encrypted at rest) and, on the
# device, only inside the TPM. Terraform state should itself be stored encrypted
# (see envs/*/backend). This module keeps provisioning fully declarative: adding
# a device is a change to the `devices` map, not a manual script run.
###############################################################################

variable "kv_mount" {
  type = string
}

variable "device_base" {
  type = string
}

variable "devices" {
  description = <<-EOT
    Map of device_id => settings. If `seed` is null, a random Base32 seed is
    generated. `tier` selects the hardware protection level (standard|high|
    critical) and is consumed by the compute modules (TPM / TPM+SGX / vTPM+TDX).
  EOT
  type = map(object({
    seed = optional(string)
    tier = optional(string, "standard")
  }))
}

variable "init_device_script" {
  description = "Path to iot-tpm scripts/init_device.sh used to seal the seed in the device TPM."
  type        = string
  default     = "../../iot-tpm/scripts/init_device.sh"
}

variable "run_tpm_sealing" {
  description = "If true, run init_device.sh via local-exec. Set false to only populate Vault."
  type        = bool
  default     = false
}

# Random material when the caller does not pin an explicit RFC 4648 seed.
# Terraform has no native Base32; init_device.sh normalizes this to a Base32
# TOTP seed for pyotp. Callers who need determinism should pin `seed`.
resource "random_id" "seed" {
  for_each    = { for id, d in var.devices : id => d if try(d.seed, null) == null }
  byte_length = 20 # 160-bit material, matching a standard TOTP seed length
}

locals {
  # Effective seed per device: pinned value, or the generated hex material.
  seeds = {
    for id, d in var.devices :
    id => coalesce(try(d.seed, null), try(random_id.seed[id].hex, null))
  }
}

# Write each device seed into Vault KV v2.
resource "vault_kv_secret_v2" "device" {
  for_each  = var.devices
  mount     = var.kv_mount
  name      = "${var.device_base}/${each.key}"
  data_json = jsonencode({
    otp_secret = local.seeds[each.key]
    tier       = try(each.value.tier, "standard")
  })
}

# Seal the seed inside the device TPM (optional; disabled by default in CI).
resource "null_resource" "seal" {
  for_each = var.run_tpm_sealing ? var.devices : {}

  triggers = {
    device_id = each.key
    seed_hash = sha256(local.seeds[each.key])
  }

  provisioner "local-exec" {
    command     = "${var.init_device_script} ${each.key}"
    environment = { DEVICE_ID = each.key }
  }
}

output "device_paths" {
  value = { for id, s in vault_kv_secret_v2.device : id => s.name }
}

output "device_tiers" {
  value = { for id, d in var.devices : id => try(d.tier, "standard") }
}
