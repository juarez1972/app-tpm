#!/bin/bash
echo "=== CORREÇÃO DO DOCKER-COMPOSE.YML ==="

# Backup do arquivo atual
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)

# Criar novo docker-compose.yml corrigido
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
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=temp-root-token
    volumes:
      - ./vault-data:/vault/data
    cap_add:
      - IPC_LOCK
    networks:
      - tpm-vault-network
    restart: unless-stopped
    command: ["vault", "server", "-dev", "-dev-root-token-id=temp-root-token", "-dev-listen-address=0.0.0.0:8200"]

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

echo "✅ docker-compose.yml corrigido"

# Parar e reiniciar serviços
echo "Reiniciando serviços..."
docker-compose down
docker-compose up -d --build

echo "Aguardando inicialização..."
sleep 15

echo "Verificando status:"
docker-compose ps

echo "Testando Vault:"
curl -s http://localhost:8200/v1/sys/health > /dev/null && echo "✅ Vault ONLINE" || echo "❌ Vault OFFLINE"

echo "=== CORREÇÃO CONCLUÍDA ==="
