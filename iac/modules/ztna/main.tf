###############################################################################
# Module: ztna (Twingate)
#
# Formalizes as code the Twingate resources that were previously only described
# in ztna/README.md. Publishes the internal services (Vault + IoT server) with
# NO inbound port open, enforcing identity-based access (mitigates lateral
# movement, MITRE T1021).
#
# The on-prem Connector container itself is launched by the compose-stack module;
# here we declare the Twingate Cloud objects: remote network, resources, and the
# access group bound to them.
###############################################################################

variable "remote_network_name" {
  type    = string
  default = "ppgia96"
}

variable "vault_address" {
  description = "Internal address of the Vault service reachable by the connector."
  type        = string
  default     = "vault.internal.ppgia96"
}

variable "iot_server_address" {
  description = "Internal address of the IoT auth server reachable by the connector."
  type        = string
  default     = "iot-server.internal.ppgia96"
}

variable "access_group_name" {
  type    = string
  default = "app-tpm-operators"
}

resource "twingate_remote_network" "onprem" {
  name = var.remote_network_name
}

resource "twingate_connector" "onprem" {
  remote_network_id = twingate_remote_network.onprem.id
  name              = "${var.remote_network_name}-connector"
}

# Generate connector tokens consumed by the compose-stack connector container.
resource "twingate_connector_tokens" "onprem" {
  connector_id = twingate_connector.onprem.id
}

resource "twingate_group" "operators" {
  name = var.access_group_name
}

# Resource 1: Vault (no inbound port; reachable only through the ZTNA).
resource "twingate_resource" "vault" {
  name              = "app-tpm-vault"
  address           = var.vault_address
  remote_network_id = twingate_remote_network.onprem.id

  protocols = {
    allow_icmp = false
    tcp = {
      policy = "RESTRICTED"
      ports  = ["8200"]
    }
    udp = { policy = "DENY_ALL" }
  }

  access_group {
    group_id = twingate_group.operators.id
  }
}

# Resource 2: IoT auth server.
resource "twingate_resource" "iot_server" {
  name              = "app-tpm-iot-server"
  address           = var.iot_server_address
  remote_network_id = twingate_remote_network.onprem.id

  protocols = {
    allow_icmp = false
    tcp = {
      policy = "RESTRICTED"
      ports  = ["5000", "8883"]
    }
    udp = { policy = "DENY_ALL" }
  }

  access_group {
    group_id = twingate_group.operators.id
  }
}

output "connector_tokens" {
  description = "Access/refresh tokens for the on-prem connector container."
  value = {
    access_token  = twingate_connector_tokens.onprem.access_token
    refresh_token = twingate_connector_tokens.onprem.refresh_token
  }
  sensitive = true
}

output "published_resources" {
  value = [twingate_resource.vault.name, twingate_resource.iot_server.name]
}
