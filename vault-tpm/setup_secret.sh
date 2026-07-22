#!/usr/bin/env bash
#
# setup_secret.sh — Smoke-test do Vault: escreve e lê um segredo de exemplo
# em secret/data/tpm-verified/*, autenticando com o token recuperado do TPM.
#
# NÃO gera mais token/segredo em texto claro. No desenho de produção deste
# projeto, o root token (e os demais) ficam SELADOS no TPM — ver:
#   - scripts/get_root_token.sh      (recupera o token do TPM, só no stdout)
#   - scripts/revoke_root_token.sh   (cria token de menor privilégio + revoga o root)
#
# Uso:
#   cd vault-tpm
#   export VAULT_ADDR="http://127.0.0.1:8201"          # porta do host -> container
#   ./setup_secret.sh                                   # usa o token do TPM
#   VAULT_TOKEN=hvs.xxxx ./setup_secret.sh              # ou um token já em mãos
#
# Por padrão, prefere o token de menor privilégio (app_token) se ele existir
# no TPM; caso contrário, cai para o root token. Você pode forçar qual usar:
#   TOKEN_BASENAME=root_token ./setup_secret.sh
#
# Variáveis de ambiente:
#   VAULT_ADDR       (default: http://127.0.0.1:8201)
#   VAULT_TOKEN      (se definido, é usado diretamente; pula a recuperação do TPM)
#   TOKEN_BASENAME   (default: auto — app_token se existir, senão root_token)
#   TPM_DATA_DIR     (default: ./tpm-data)
#   TPM2TOOLS_TCTI   (default: device:/dev/tpmrm0 ; use swtpm:path=... em VM/CI)
#   TPM_SRK_HANDLE   (default: 0x81010001)
#   KV_MOUNT         (default: secret)
#   SECRET_PATH      (default: tpm-verified/exemplo)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8201}"
TPM_DATA_DIR="${TPM_DATA_DIR:-${SCRIPT_DIR}/tpm-data}"
TCTI="${TPM2TOOLS_TCTI:-device:/dev/tpmrm0}"
SRK_HANDLE="${TPM_SRK_HANDLE:-0x81010001}"
KV_MOUNT="${KV_MOUNT:-secret}"
SECRET_PATH="${SECRET_PATH:-tpm-verified/exemplo}"

echo "=== SMOKE-TEST DO VAULT (escrita/leitura de segredo) ==="

# ---------------------------------------------------------------------------
# 1. Obtém um token — do ambiente ou recuperando do TPM (sem texto claro)
# ---------------------------------------------------------------------------
if [ -n "${VAULT_TOKEN:-}" ]; then
  echo "[INFO] usando VAULT_TOKEN do ambiente."
else
  # Escolhe automaticamente o token de menor privilégio, se existir.
  if [ -z "${TOKEN_BASENAME:-}" ]; then
    if [ -f "${TPM_DATA_DIR}/app_token.enc.pub" ]; then
      TOKEN_BASENAME="app_token"
    else
      TOKEN_BASENAME="root_token"
    fi
  fi
  echo "[INFO] recuperando token do TPM (${TOKEN_BASENAME})…"
  VAULT_TOKEN="$(TPM_DATA_DIR="${TPM_DATA_DIR}" TPM2TOOLS_TCTI="${TCTI}" \
    TPM_SRK_HANDLE="${SRK_HANDLE}" TOKEN_BASENAME="${TOKEN_BASENAME}" \
    bash "${SCRIPT_DIR}/scripts/get_root_token.sh" --quiet)"
fi
[ -n "${VAULT_TOKEN}" ] || { echo "[FAIL] não consegui obter um token do Vault." >&2; exit 4; }
export VAULT_TOKEN

# ---------------------------------------------------------------------------
# 2. Garante o engine KV v2 em ${KV_MOUNT}/ (idempotente)
# ---------------------------------------------------------------------------
mounts="$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/mounts")"
if ! echo "${mounts}" | python3 -c "import sys,json;m=json.load(sys.stdin);sys.exit(0 if '${KV_MOUNT}/' in m else 1)" 2>/dev/null; then
  echo "[INFO] montando KV v2 em '${KV_MOUNT}/'…"
  curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" -X POST \
    -d '{"type":"kv","options":{"version":"2"}}' \
    "${VAULT_ADDR}/v1/sys/mounts/${KV_MOUNT}" >/dev/null || true
fi

# ---------------------------------------------------------------------------
# 3. Escreve um segredo de exemplo
# ---------------------------------------------------------------------------
echo "[INFO] escrevendo segredo de exemplo em ${KV_MOUNT}/data/${SECRET_PATH}…"
code="$(curl -s -o /tmp/setup_secret_w.$$ -w '%{http_code}' \
  -H "X-Vault-Token: ${VAULT_TOKEN}" -X POST \
  -d '{"data":{"exemplo":"valor-de-teste","origem":"setup_secret.sh"}}' \
  "${VAULT_ADDR}/v1/${KV_MOUNT}/data/${SECRET_PATH}")"
rm -f /tmp/setup_secret_w.$$
if [ "${code}" != "200" ] && [ "${code}" != "204" ]; then
  echo "[FAIL] escrita falhou (HTTP ${code})." >&2; exit 5
fi
echo "[ OK ] segredo escrito."

# ---------------------------------------------------------------------------
# 4. Lê o segredo de volta
# ---------------------------------------------------------------------------
echo "[INFO] lendo o segredo de volta…"
read_out="$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" \
  "${VAULT_ADDR}/v1/${KV_MOUNT}/data/${SECRET_PATH}")"
if echo "${read_out}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['data']['data'])" 2>/dev/null; then
  echo "[ OK ] leitura confirmada."
else
  echo "[FAIL] não consegui ler o segredo de volta: ${read_out}" >&2; exit 6
fi

echo
echo "=== SMOKE-TEST CONCLUÍDO: escrita e leitura no Vault funcionando ==="
echo "Nenhum token ou segredo foi gravado em texto claro — o token veio do TPM."
