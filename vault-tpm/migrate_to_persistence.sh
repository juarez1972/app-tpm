#!/bin/bash
echo "=== MIGRAÇÃO PARA MODO PERSISTENTE ==="

# Parar tudo
echo "1. Parando serviços..."
docker-compose down

# Backup dos dados atuais
echo "2. Fazendo backup dos dados atuais..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
cp -r tpm-data/ $BACKUP_DIR/ 2>/dev/null || true
echo "Backup criado em: $BACKUP_DIR"

# Limpar e preparar diretórios
echo "3. Preparando diretórios de dados..."
sudo rm -rf vault-data
mkdir -p vault-data
chmod 755 vault-data

# Verificar se o vault-config.hcl existe
if [ ! -f vault-config.hcl ]; then
    echo "4. Criando vault-config.hcl..."
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
else
    echo "4. vault-config.hcl já existe"
fi

# Iniciar serviços
echo "5. Iniciando serviços em modo persistente..."
docker-compose up -d --build

# Aguardar inicialização
echo "6. Aguardando inicialização..."
for i in {1..30}; do
    if curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; then
        echo "✅ Vault está respondendo!"
        break
    fi
    echo "Aguardando Vault... ($i/30)"
    sleep 2
done

# Verificar persistência
echo "7. Verificando persistência..."
echo "Conteúdo de vault-data:"
ls -la vault-data/

echo "8. Testando escrita e leitura..."
# Escrever um secret
curl -H "X-Vault-Token: temp-root-token" \
  -X POST \
  -d '{"data": {"persistence": "teste-de-persistencia"}}' \
  http://localhost:8200/v1/secret/data/persistence-test > /dev/null 2>&1

# Ler o secret
curl -H "X-Vault-Token: temp-root-token" \
  http://localhost:8200/v1/secret/data/persistence-test 2>/dev/null | jq '.data.data' || echo "Erro na leitura"

echo "9. Verificando logs..."
docker-compose logs vault --tail=5

echo "=== MIGRAÇÃO CONCLUÍDA ==="
