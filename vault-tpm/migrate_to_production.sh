#!/bin/bash
echo "=== MIGRAÇÃO PARA MODO PRODUÇÃO ==="

echo "1. Parando serviços..."
docker-compose down

echo "2. Backup dos dados atuais..."
cp -r tpm-data tpm-data-backup-$(date +%Y%m%d_%H%M%S)

echo "3. Criando configuração de produção..."
cat > vault-config.hcl << 'EOF'
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}

ui = true
api_addr = "http://vault:8200"
EOF

echo "4. Atualizando docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
services:
  tpm-validator:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - /dev/tpm0:/dev/tpm0
      - ./tpm-data:/app/tpm-data
    environment:
      - VAULT_ADDR=http://vault:8200
    networks:
      - tpm-vault-network
    restart: unless-stopped

  vault:
    image: vault:1.13.3
    ports:
      - "8200:8200"
    volumes:
      - ./vault-data:/vault/data
      - ./vault-config.hcl:/vault/config/vault-config.hcl
    cap_add:
      - IPC_LOCK
    networks:
      - tpm-vault-network
    restart: unless-stopped
    command: server -config /vault/config/vault-config.hcl

  vault-initializer:
    build: ./vault-init
    environment:
      - TPM_VALIDATOR_URL=http://tpm-validator:5000
      - VAULT_ADDR=http://vault:8200
    volumes:
      - ./tpm-data:/app/tpm-data
    networks:
      - tpm-vault-network
    restart: unless-stopped
    depends_on:
      - vault

networks:
  tpm-vault-network:
    driver: bridge
EOF

echo "5. Reconstruindo serviços..."
docker-compose build --no-cache
docker-compose up -d

echo "6. Aguardando inicialização..."
sleep 20

echo "7. Verificando status..."
docker-compose ps

echo "8. O Vault deve estar inicializado e unsealed automaticamente"
echo "   As chaves de unseal e token root estarão protegidos pelo TPM"

echo "=== MIGRAÇÃO CONCLUÍDA ==="
echo "📁 Estrutura de arquivos protegidos:"
echo "   tpm-data/secret              # Segredo do TPM"
echo "   tpm-data/vault-unseal-keys.enc # Chaves de unseal criptografadas"
echo "   tpm-data/vault-root-token.enc  # Token root criptografado"
