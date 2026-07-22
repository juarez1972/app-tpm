#!/bin/bash
echo "=== VALIDAÇÃO DO SISTEMA TPM + VAULT ==="

# Endereço do Vault (porta do host mapeada para o container).
VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
KV_MOUNT="${KV_MOUNT:-secret}"

# Recupera o token do TPM (sem texto claro). Prefere o token de menor
# privilégio (app_token) se ele existir; senão usa o root. Pode-se sobrescrever
# exportando VAULT_TOKEN antes de rodar.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPM_DATA_DIR="${TPM_DATA_DIR:-${SCRIPT_DIR}/tpm-data}"
if [ -z "${VAULT_TOKEN:-}" ]; then
  if [ -z "${TOKEN_BASENAME:-}" ]; then
    if [ -f "${TPM_DATA_DIR}/app_token.enc.pub" ]; then TOKEN_BASENAME="app_token"; else TOKEN_BASENAME="root_token"; fi
  fi
  VAULT_TOKEN="$(TPM_DATA_DIR="${TPM_DATA_DIR}" TOKEN_BASENAME="${TOKEN_BASENAME}" \
    bash "${SCRIPT_DIR}/scripts/get_root_token.sh" --quiet 2>/dev/null || true)"
fi

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

if [ -z "${VAULT_TOKEN}" ]; then
  echo -e "\n5-6. (pulando escrita/leitura: nenhum token disponível no TPM ainda)"
else
  echo -e "\n5. Testando escrita no Vault..."
  curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" \
    -X POST \
    -d '{"data": {"exemplo": "valor-de-teste"}}' \
    "${VAULT_ADDR}/v1/${KV_MOUNT}/data/tpm-verified/test"

  echo -e "\n6. Testando leitura do Vault..."
  curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" \
    "${VAULT_ADDR}/v1/${KV_MOUNT}/data/tpm-verified/test" | jq .
fi

echo -e "\n=== VALIDAÇÃO CONCLUÍDA ==="
