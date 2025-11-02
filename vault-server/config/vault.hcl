# Habilita a interface de usuário (UI)
ui = true

# Define o backend de armazenamento como "file"
# O caminho aponta para dentro do container, que será mapeado para um volume Docker.
storage "file" {
  path = "/vault/file"
}

# Define o "ouvinte" (listener) de rede
listener "tcp" {
  # Ouve em todas as interfaces dentro do container na porta 8200
  address = "0.0.0.0:8200"

  # IMPORTANTE: Desabilita o TLS.
  # Em um ambiente de produção real, você NUNCA faria isso.
  # Você configuraria certificados TLS (tls_cert_file, tls_key_file).
  tls_disable = 1
}
