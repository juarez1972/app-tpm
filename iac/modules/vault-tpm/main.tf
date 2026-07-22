###############################################################################
# Module: vault-tpm
#
# Declares the Vault-side objects that back the IoT authentication scheme:
#   - a KV v2 secrets engine (default mount "secret")
#   - the "app-policy" that scopes access to tpm-verified/*
#   - (optionally) an AppRole for the IoT server to read device secrets
#
# The Vault ROOT token itself is NOT managed here: it is sealed under the TPM
# Storage Root Key by the vault-tpm initializer and never appears in Terraform
# state. This module authenticates with a scoped token/AppRole supplied by the
# environment (see envs/*/backend and variables).
###############################################################################

variable "kv_mount" {
  description = "KV v2 mount point for device secrets."
  type        = string
  default     = "secret"
}

variable "device_base" {
  description = "Logical path prefix (under the KV mount) for per-device secrets."
  type        = string
  default     = "tpm-verified/iot/devices"
}

variable "enable_approle" {
  description = "Create an AppRole for the IoT server instead of using a raw token."
  type        = bool
  default     = true
}

# KV v2 engine (idempotent: import if it already exists in a live Vault).
resource "vault_mount" "kv" {
  path        = var.kv_mount
  type        = "kv"
  options     = { version = "2" }
  description = "app-tpm device secrets (TOTP seeds) — KV v2"
}

# Policy: read-only access to the tpm-verified subtree only.
resource "vault_policy" "app_policy" {
  name   = "app-policy"
  policy = <<-EOT
    # Read TOTP seeds for provisioned devices.
    path "${var.kv_mount}/data/tpm-verified/*" {
      capabilities = ["read"]
    }
    path "${var.kv_mount}/metadata/tpm-verified/*" {
      capabilities = ["read", "list"]
    }
  EOT
}

# AppRole for the IoT server (preferred over a long-lived root token).
resource "vault_auth_backend" "approle" {
  count = var.enable_approle ? 1 : 0
  type  = "approle"
}

resource "vault_approle_auth_backend_role" "iot_server" {
  count          = var.enable_approle ? 1 : 0
  backend        = vault_auth_backend.approle[0].path
  role_name      = "iot-server"
  token_policies = [vault_policy.app_policy.name]
  token_ttl      = 3600
  token_max_ttl  = 14400
}

output "kv_mount" {
  value = vault_mount.kv.path
}

output "device_base" {
  value = var.device_base
}

output "policy_name" {
  value = vault_policy.app_policy.name
}

output "approle_role_name" {
  value = var.enable_approle ? vault_approle_auth_backend_role.iot_server[0].role_name : null
}
