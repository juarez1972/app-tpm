# Política para o serviço de inicialização
path "sys/seal-status" {
  capabilities = ["read"]
}

path "sys/unseal" {
  capabilities = ["update"]
}

path "sys/health" {
  capabilities = ["read"]
}

path "sys/init" {
  capabilities = ["update"]
}

path "secret/data/tpm-verified/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
