#!/bin/bash
echo "=== VERIFICAÇÃO DE PERSISTÊNCIA ==="

echo -e "\n1. Estado atual do Vault:"
curl -s http://localhost:8200/v1/sys/health | jq '{initialized, sealed}'

echo -e "\n2. Conteúdo de vault-data:"
ls -la vault-data/

echo -e "\n3. Escrevendo secret de teste..."
curl -H "X-Vault-Token: $(cat tpm-data/vault-root-token 2>/dev/null || echo 'temp-root-token')" \
  -X POST \
  -d '{"data": {"persistence_test": "dados-persistentes"}}' \
  http://localhost:8200/v1/secret/data/persistence-test > /dev/null 2>&1

echo -e "\n4. Reiniciando serviços..."
docker-compose restart vault vault-initializer
sleep 10

echo -e "\n5. Estado após reinicialização:"
curl -s http://localhost:8200/v1/sys/health | jq '{initialized, sealed}'

echo -e "\n6. Lendo secret após reinicialização:"
curl -H "X-Vault-Token: $(cat tpm-data/vault-root-token 2>/dev/null || echo 'temp-root-token')" \
  http://localhost:8200/v1/secret/data/persistence-test 2>/dev/null | jq '.data.data' || echo "Secret não encontrado"

echo -e "\n7. Conteúdo atual de vault-data:"
ls -la vault-data/
