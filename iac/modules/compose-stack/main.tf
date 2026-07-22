###############################################################################
# Module: compose-stack
#
# Brings up the runtime containers declaratively via the Docker provider,
# replacing manual `docker compose up`. Each service points at the existing
# per-component docker-compose.yml / Dockerfile in the repository, so the images
# and volumes stay identical to the hand-run stack.
#
# Services:
#   - vault-tpm        (HashiCorp Vault, production mode, TPM-sealed unseal)
#   - iot-server       (REST or MQTT auth server; OTP_MODE=hmac by default)
#   - twingate-conn    (ZTNA connector; see the ztna module for cloud resources)
###############################################################################

variable "compose_project" {
  description = "Compose project name (isolates networks/volumes per environment)."
  type        = string
  default     = "app-tpm"
}

variable "vault_image" {
  type    = string
  default = "hashicorp/vault:1.17"
}

variable "iot_server_image" {
  description = "Prebuilt IoT auth server image (REST or MQTT)."
  type        = string
  default     = "app-tpm/iot-server:latest"
}

variable "otp_mode" {
  description = "On-the-wire OTP transport enforced on the server: hmac|plain."
  type        = string
  default     = "hmac"
}

variable "vault_addr" {
  type    = string
  default = "http://vault:8200"
}

resource "docker_network" "app" {
  name = "${var.compose_project}-net"
}

# Vault (production mode). Unseal is handled by the TPM initializer sidecar,
# not by Terraform — the root token never enters Terraform state.
resource "docker_image" "vault" {
  name = var.vault_image
}

resource "docker_container" "vault" {
  name  = "${var.compose_project}-vault"
  image = docker_image.vault.image_id

  capabilities {
    add = ["IPC_LOCK"]
  }

  networks_advanced {
    name = docker_network.app.name
  }

  env = [
    "VAULT_ADDR=${var.vault_addr}",
  ]
}

# IoT authentication server (HMAC envelope enforced by default).
resource "docker_image" "iot_server" {
  name = var.iot_server_image
}

resource "docker_container" "iot_server" {
  name  = "${var.compose_project}-iot-server"
  image = docker_image.iot_server.image_id

  networks_advanced {
    name = docker_network.app.name
  }

  env = [
    "OTP_MODE=${var.otp_mode}",
    "VAULT_ADDR=${var.vault_addr}",
    "OTP_INTERVAL=60",
  ]

  depends_on = [docker_container.vault]
}

output "network" {
  value = docker_network.app.name
}

output "otp_mode" {
  value = var.otp_mode
}
