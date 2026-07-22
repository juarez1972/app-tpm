###############################################################################
# app-tpm — Infrastructure as Code (Terraform) — provider requirements
#
# All provisioning for the hybrid Zero-Trust architecture (vault-tpm, iot-tpm,
# ztna) is declared here so that the entire stack is reproducible from code.
# Nothing is provisioned by hand: Vault policies/mounts, per-device secrets,
# the Docker Compose stack, and the Twingate ZTNA resources are all managed by
# Terraform.
###############################################################################

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 4.2"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    twingate = {
      source  = "Twingate/twingate"
      version = "~> 3.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
