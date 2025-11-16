#!/bin/bash
echo "=== CONFIGURAÇÃO DA INTERFACE GRAFICA DO VAULT ==="

# Obter token
TOKEN=$(cat tpm-data/vault-root-token)
echo "Token Root: $TOKEN"

# Verificar se UI está ativada
echo -e "\n1. Verificando status da UI..."
UI_STATUS=$(curl -s -H "X-Vault-Token: $TOKEN" http://localhost:8200/v1/sys/config/ui | jq -r '.data.ui')

if [ "$UI_STATUS" = "true" ]; then
    echo "✅ UI já está ativada"
else
    echo "⚠️ Ativando UI..."
    curl -s -H "X-Vault-Token: $TOKEN" \
      -X PUT \
      -d '{"ui": true}' \
      http://localhost:8200/v1/sys/config/ui
    echo "✅ UI ativada"
fi

# Criar alguns secrets para testar na UI
echo -e "\n2. Criando dados de teste para a UI..."
curl -s -H "X-Vault-Token: $TOKEN" \
  -X POST \
  -d '{"data": {"username": "admin", "password": "senha-secreta-123", "url": "http://api.exemplo.com"}}' \
  http://localhost:8200/v1/secret/data/app/database

curl -s -H "X-Vault-Token: $TOKEN" \
  -X POST \
  -d '{"data": {"api_key": "ak_123456789", "secret_key": "sk_987654321"}}' \
  http://localhost:8200/v1/secret/data/app/external-api

echo -e "\n3. Informações para acesso:"
echo "📋 URL: http://localhost:8200"
echo "🔑 Token: $TOKEN"
echo "📁 Secrets criados:"
echo "   - secret/data/app/database"
echo "   - secret/data/app/external-api"

echo -e "\n4. Testando acesso..."
curl -s http://localhost:8200/ui/ > /dev/null && echo "✅ Interface web está respondendo" || echo "❌ Interface web não está acessível"

echo -e "\n=== CONFIGURAÇÃO CONCLUÍDA ==="
echo "Acesse: http://localhost:8200"
echo "Use o token: $TOKEN"
