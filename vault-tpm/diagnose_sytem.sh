#!/bin/bash
echo "=== DIAGNÓSTICO COMPLETO DO SISTEMA ==="

echo -e "\n1. VERIFICANDO CONTAINERS:"
docker-compose ps -a

echo -e "\n2. VERIFICANDO PROCESSOS NA PORTA 8200:"
sudo lsof -i :8200 || echo "Nenhum processo encontrado na porta 8200"

echo -e "\n3. VERIFICANDO REDES DOCKER:"
docker network ls | grep tpm-vault

echo -e "\n4. VERIFICANDO LOGS DO VAULT:"
docker-compose logs vault --tail=20

echo -e "\n5. VERIFICANDO LOGS DO VAULT-INITIALIZER:"
docker-compose logs vault-initializer --tail=10

echo -e "\n6. TESTANDO CONEXÕES:"
echo "TPM Validator:"
curl -s -m 5 http://localhost:5000/status > /dev/null && echo "✅ ONLINE" || echo "❌ OFFLINE"

echo "Vault:"
curl -s -m 5 http://localhost:8200/v1/sys/health > /dev/null && echo "✅ ONLINE" || echo "❌ OFFLINE"

echo -e "\n7. VERIFICANDO VOLUMES:"
echo "TPM Data:"
ls -la tpm-data/ 2>/dev/null || echo "Diretório tpm-data não existe"
echo "Vault Data:"
ls -la vault-data/ 2>/dev/null || echo "Diretório vault-data não existe"

echo -e "\n8. VERIFICANDO IMAGENS:"
docker images | grep -E "(vault|tpm-validator|vault-initializer)"

echo "=== DIAGNÓSTICO CONCLUÍDO ==="
