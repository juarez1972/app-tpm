#!/bin/bash
echo "=== VALIDAÇÃO DO SISTEMA TPM + VAULT ==="

echo -e "\n1. Validando TPM..."
TPM_STATUS=$(curl -s http://localhost:5000/status)
echo "$TPM_STATUS" | jq .

echo -e "\n2. Validando Vault..."
VAULT_STATUS=$(curl -s http://localhost:8200/v1/sys/health)
echo "$VAULT_STATUS" | jq .

echo -e "\n3. Verificando logs do initializer..."
docker-compose logs vault-initializer --tail=10

echo -e "\n4. Verificando dados persistentes..."
echo "Vault data: $(ls -la vault-data/ | wc -l) arquivos"
echo "TPM data: $(ls -la tpm-data/ | wc -l) arquivos"

echo -e "\n5. Testando escrita no Vault..."
curl -H "X-Vault-Token: temp-root-token" \
  -X POST \
  -d '{"data": {"secret": "minha-senha-super-secreta"}}' \
  http://localhost:8200/v1/secret/data/tpm-verified/test

echo -e "\n6. Testando leitura do Vault..."
curl -H "X-Vault-Token: temp-root-token" \
  http://localhost:8200/v1/secret/data/tpm-verified/test | jq .

echo -e "\n=== VALIDAÇÃO CONCLUÍDA ==="
