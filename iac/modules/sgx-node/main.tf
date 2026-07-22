###############################################################################
# Module: sgx-node
#
# Provisions the confidential-compute node that runs the Vault initializer inside
# an Intel SGX enclave (via Gramine). This is the "critical" tier of the IaC
# sensitivity model: only the most sensitive secret-handling script — the Vault
# unseal/root-token initializer — runs shielded in an enclave with CPU-encrypted
# memory and remote attestation (DCAP).
#
# See ../../sgx/README.md for the enclave design, the Gramine manifest, and the
# attestation flow. This module wires that image into a Docker container with the
# SGX device mounted, gated on `tier == "critical"`.
###############################################################################

variable "enabled" {
  description = "Provision the SGX node (true only where a critical tier device exists)."
  type        = bool
  default     = false
}

variable "gramine_image" {
  description = "Prebuilt Gramine-SGX image for the Vault initializer (sgx/Dockerfile.gramine)."
  type        = string
  default     = "app-tpm/vault-initializer-sgx:latest"
}

variable "sgx_device" {
  description = "SGX device node exposed to the enclave container."
  type        = string
  default     = "/dev/sgx_enclave"
}

variable "sgx_provision_device" {
  description = "SGX provisioning device required for DCAP attestation."
  type        = string
  default     = "/dev/sgx_provision"
}

variable "aesmd_socket" {
  description = "Host path to the AESM socket used for quote generation."
  type        = string
  default     = "/var/run/aesmd/aesm.socket"
}

variable "network_name" {
  type    = string
  default = "app-tpm-net"
}

resource "docker_image" "vault_initializer_sgx" {
  count = var.enabled ? 1 : 0
  name  = var.gramine_image
}

resource "docker_container" "vault_initializer_sgx" {
  count = var.enabled ? 1 : 0
  name  = "app-tpm-vault-init-sgx"
  image = docker_image.vault_initializer_sgx[0].image_id

  # Expose the SGX enclave + provisioning devices to the container.
  devices {
    host_path = var.sgx_device
  }
  devices {
    host_path = var.sgx_provision_device
  }

  # AESM socket for DCAP quote generation (remote attestation).
  mounts {
    type      = "bind"
    source    = var.aesmd_socket
    target    = "/var/run/aesmd/aesm.socket"
    read_only = false
  }

  networks_advanced {
    name = var.network_name
  }

  env = [
    "SGX=1",
    "GRAMINE_ATTESTATION=dcap",
  ]
}

output "enabled" {
  value = var.enabled
}

output "container_name" {
  value = var.enabled ? docker_container.vault_initializer_sgx[0].name : null
}
