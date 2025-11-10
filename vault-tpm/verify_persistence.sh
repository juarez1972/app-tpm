#!/bin/bash
echo "=== VERIFICAÇÃO DE PERSISTÊNCIA ==="

echo -e "\n1. Estado atual:"
docker-compose ps

echo -e "\n2. Dados em vault-data:"
find vault-data -type f | head -10

echo -e "\n3. Teste de reinicialização..."
echo "Parando serviços..."
docker-compose stop vault vault-initializer

echo "Conteúdo de vault-data após parada:"
find vault-data -type f | wc -l

echo "Reiniciando serviços..."
docker-compose start vault vault-initializer

sleep 10

echo -e "\n4. Estado após reinicialização:"
curl -s http://localhost:8200/v1/sys/health | jq '{initialized, sealed}'

echo -e "\n5. Tentando ler secret após reinicialização:"
curl -H "X-Vault-Token: temp-root-token" \
  http://localhost:8200/v1/secret/data/persistence-test 2>/dev/null | jq '.data.data' || echo "Secret não encontrado"

echo -e "\n6. Dados finais em vault-data:"
find vault-data -type f | head -10
echo "Total de arquivos: $(find vault-data -type f | wc -l)"
