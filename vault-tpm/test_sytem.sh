#!/bin/bash
echo "=== TESTE DO SISTEMA TPM + VAULT ==="

echo -e "\n1. Testando TPM Validator..."
TPM_STATUS=$(curl -s http://localhost:5000/status)
echo "TPM Status:"
echo "$TPM_STATUS" | jq .

echo -e "\n2. Testando Vault Health..."
VAULT_HEALTH=$(curl -s http://localhost:8200/v1/sys/health)
echo "Vault Health:"
echo "$VAULT_HEALTH" | jq .

echo -e "\n3. Testando Vault Seal Status..."
VAULT_SEAL=$(curl -s http://localhost:8200/v1/sys/seal-status)
echo "Vault Seal Status:"
echo "$VAULT_SEAL" | jq .

echo -e "\n4. Verificando logs do vault-initializer..."
docker-compose logs vault-initializer --tail=20

echo -e "\n5. Verificando dados persistentes..."
echo "Vault data:"
ls -la vault-data/
echo -e "\nTPM data:"
ls -la tpm-data/

echo -e "\n=== TESTE CONCLUÍDO ==="
