# vault.hcl
# Configura o armazenamento em 'file' para persistência
storage "file" {
  path = "/vault/file" # [31]
}

# Configura o listener da API
listener "tcp" {
  address     = "0.0.0.0:8200" # [9]
  tls_disable = "true"         # 
}

# Habilita a UI
ui = true

# Desabilita mlock (trava de memória) se IPC_LOCK não for fornecido
# Como estamos usando 'cap_add', definimos como 'false'
disable_mlock = false # [9]
api_addr = "http://vault:8200"
cluster_addr = "http://vault:8201"
