#!/usr/bin/env bash
#
# revoke_root_token.sh — Cria um token de MENOR PRIVILÉGIO e, só depois de
# validá-lo, REVOGA o root token inicial do Vault.
#
# Boa prática de segurança: o root token inicial (gerado por sys/init e selado
# no TPM) tem poder total e não deve ser usado no dia a dia. Este utilitário:
#
#   1. Recupera o root token do TPM (scripts/get_root_token.sh) — nunca em disco.
#   2. Garante que o KV v2 está montado em `secret/`.
#   3. Escreve/atualiza a policy de app (scripts/setup_vault_policies.hcl -> "app-policy").
#   4. Cria um token FILHO com essa policy (renovável, TTL configurável).
#   5. VALIDA o token novo (lookup-self + escrita/leitura no path permitido).
#   6. Sela o novo token no TPM (app_token.enc/.pub/.priv) — sem texto claro.
#   7. Só então REVOGA o root token (revoke-self).
#   8. Confirma que o root deixou de funcionar (lookup-self com o root -> 403).
#
# SEGURANÇA: a revogação é IRREVERSÍVEL. Depois dela, não há mais como gerar
# um root token exceto pelo procedimento oficial de "generate-root" (que exige
# o quorum de unseal keys — que continuam seladas no TPM). Por isso o script
# só revoga após provar que o token de menor privilégio funciona.
#
# Uso:
#   cd vault-tpm
#   export VAULT_ADDR="http://127.0.0.1:8201"     # porta do host -> container
#   ./scripts/revoke_root_token.sh                 # cria app-token e revoga root
#   ./scripts/revoke_root_token.sh --dry-run       # faz tudo, MENOS revogar
#
# Recuperar depois o token de menor privilégio (selado no TPM):
#   export VAULT_TOKEN="$(TOKEN_BASENAME=app_token \
#       ./scripts/get_root_token.sh --quiet)"
#   vault token lookup            # confirma: policies=[app-policy]
#
# Variáveis de ambiente:
#   VAULT_ADDR       (default: http://127.0.0.1:8201)
#   TPM_DATA_DIR     (default: ./tpm-data)
#   TPM2TOOLS_TCTI   (default: device:/dev/tpmrm0 ; use swtpm:path=... em VM/CI)
#   TPM_SRK_HANDLE   (default: 0x81010001)
#   APP_POLICY_NAME  (default: app-policy)
#   APP_POLICY_FILE  (default: scripts/setup_vault_policies.hcl)
#   APP_TOKEN_TTL    (default: 768h)   # TTL do token de menor privilégio
#   KV_MOUNT         (default: secret) # ponto de montagem KV v2

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8201}"
TPM_DATA_DIR="${TPM_DATA_DIR:-${PROJECT_DIR}/tpm-data}"
TCTI="${TPM2TOOLS_TCTI:-device:/dev/tpmrm0}"
SRK_HANDLE="${TPM_SRK_HANDLE:-0x81010001}"
APP_POLICY_NAME="${APP_POLICY_NAME:-app-policy}"
APP_POLICY_FILE="${APP_POLICY_FILE:-${PROJECT_DIR}/scripts/setup_vault_policies.hcl}"
APP_TOKEN_TTL="${APP_TOKEN_TTL:-768h}"
KV_MOUNT="${KV_MOUNT:-secret}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YEL=$'\033[1;33m'; BLU=$'\033[0;34m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YEL=""; BLU=""; NC=""
fi
info(){ echo "${BLU}[INFO]${NC} $*"; }
ok(){ echo "${GREEN}[ OK ]${NC} $*"; }
warn(){ echo "${YEL}[WARN]${NC} $*"; }
err(){ echo "${RED}[FAIL]${NC} $*" >&2; }

for b in curl python3 tpm2_load tpm2_unseal tpm2_create; do
  command -v "$b" >/dev/null 2>&1 || { err "dependência ausente: $b"; exit 3; }
done

# jq é opcional: usamos python para JSON.
json_get() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1"; }

# API helpers -----------------------------------------------------------------
# 'api' imprime o body no stdout e grava o HTTP code em ${API_CODE_FILE}.
# Como normalmente chamamos via $(api ...) (subshell), NÃO dá para confiar numa
# variável global; por isso o código HTTP vai para um arquivo lido pelo pai.
API_CODE_FILE="$(mktemp /tmp/revoke-apicode.XXXXXX)"
API_CODE=""
trap 'rm -f "${API_CODE_FILE}" 2>/dev/null || true' EXIT
api() {  # api METHOD PATH [json-body]  -> stdout=body ; HTTP code em ${API_CODE_FILE}
  local method="$1" path="$2" body="${3:-}"
  local tmp; tmp="$(mktemp)"
  local code
  if [ -n "${body}" ]; then
    code="$(curl -s -o "${tmp}" -w '%{http_code}' -X "${method}" \
      -H "X-Vault-Token: ${VAULT_TOKEN}" -H 'Content-Type: application/json' \
      --data "${body}" "${VAULT_ADDR}/v1/${path}")"
  else
    code="$(curl -s -o "${tmp}" -w '%{http_code}' -X "${method}" \
      -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/${path}")"
  fi
  printf '%s' "${code}" > "${API_CODE_FILE}"
  cat "${tmp}"; rm -f "${tmp}"
}
# Lê o código HTTP da última chamada 'api' para ${API_CODE}.
code() { API_CODE="$(cat "${API_CODE_FILE}" 2>/dev/null || echo 000)"; }

# ---------------------------------------------------------------------------
# 1. Recupera o root token do TPM
# ---------------------------------------------------------------------------
info "recuperando o root token do TPM…"
ROOT_TOKEN="$(TPM_DATA_DIR="${TPM_DATA_DIR}" TPM2TOOLS_TCTI="${TCTI}" \
  TPM_SRK_HANDLE="${SRK_HANDLE}" bash "${SCRIPT_DIR}/get_root_token.sh" --quiet)"
[ -n "${ROOT_TOKEN}" ] || { err "não consegui recuperar o root token do TPM."; exit 4; }
export VAULT_TOKEN="${ROOT_TOKEN}"

# valida o root
out="$(api GET auth/token/lookup-self)"; code
[ "${API_CODE}" = "200" ] || { err "root token não autentica (HTTP ${API_CODE}). Vault destravado?"; exit 4; }
ok "root token válido (autenticado no Vault)."

# ---------------------------------------------------------------------------
# 2. Garante o KV v2 em ${KV_MOUNT}
# ---------------------------------------------------------------------------
info "verificando engine KV v2 em '${KV_MOUNT}/'…"
mounts="$(api GET sys/mounts)"
if echo "${mounts}" | python3 -c "import sys,json;m=json.load(sys.stdin);sys.exit(0 if '${KV_MOUNT}/' in m else 1)" 2>/dev/null; then
  ok "engine '${KV_MOUNT}/' já montado."
else
  info "montando KV v2 em '${KV_MOUNT}/'…"
  api POST "sys/mounts/${KV_MOUNT}" '{"type":"kv","options":{"version":"2"}}' >/dev/null; code
  [ "${API_CODE}" = "200" ] || [ "${API_CODE}" = "204" ] \
    || { err "falha ao montar KV (HTTP ${API_CODE})."; exit 5; }
  ok "KV v2 montado em '${KV_MOUNT}/'."
fi

# ---------------------------------------------------------------------------
# 3. Escreve a policy de menor privilégio
# ---------------------------------------------------------------------------
[ -f "${APP_POLICY_FILE}" ] || { err "policy não encontrada: ${APP_POLICY_FILE}"; exit 6; }
info "aplicando policy '${APP_POLICY_NAME}' a partir de ${APP_POLICY_FILE}…"
POLICY_JSON="$(python3 -c "import json,sys;print(json.dumps({'policy':open(sys.argv[1]).read()}))" "${APP_POLICY_FILE}")"
api PUT "sys/policies/acl/${APP_POLICY_NAME}" "${POLICY_JSON}" >/dev/null; code
[ "${API_CODE}" = "200" ] || [ "${API_CODE}" = "204" ] \
  || { err "falha ao escrever a policy (HTTP ${API_CODE})."; exit 6; }
ok "policy '${APP_POLICY_NAME}' aplicada."

# ---------------------------------------------------------------------------
# 4. Cria o token filho de menor privilégio
# ---------------------------------------------------------------------------
info "criando token de menor privilégio (policy=${APP_POLICY_NAME}, ttl=${APP_TOKEN_TTL})…"
CREATE_BODY="$(python3 -c "import json;print(json.dumps({'policies':['${APP_POLICY_NAME}'],'ttl':'${APP_TOKEN_TTL}','renewable':True,'display_name':'app-least-privilege','no_parent':True}))")"
created="$(api POST auth/token/create "${CREATE_BODY}")"; code
[ "${API_CODE}" = "200" ] || { err "falha ao criar token (HTTP ${API_CODE}): ${created}"; exit 7; }
APP_TOKEN="$(echo "${created}" | json_get "['auth']['client_token']")"
[ -n "${APP_TOKEN}" ] && [ "${APP_TOKEN}" != "None" ] || { err "token criado veio vazio."; exit 7; }
ok "token de menor privilégio criado."

# ---------------------------------------------------------------------------
# 5. VALIDA o token novo (lookup + escrita/leitura no path permitido)
# ---------------------------------------------------------------------------
info "validando o token de menor privilégio…"
SAVED_ROOT="${VAULT_TOKEN}"
export VAULT_TOKEN="${APP_TOKEN}"

out="$(api GET auth/token/lookup-self)"; code
[ "${API_CODE}" = "200" ] || { err "app-token não autentica (HTTP ${API_CODE})."; exit 8; }
pols="$(echo "${out}" | json_get "['data']['policies']")"
echo "${pols}" | grep -q "${APP_POLICY_NAME}" || { err "app-token sem a policy esperada: ${pols}"; exit 8; }
ok "app-token autentica; policies=${pols}."

# escrita + leitura num path coberto pela policy (secret/data/tpm-verified/*)
TEST_PATH="${KV_MOUNT}/data/tpm-verified/ci-check"
api POST "${TEST_PATH}" '{"data":{"canary":"ok"}}' >/dev/null; code
if [ "${API_CODE}" = "200" ] || [ "${API_CODE}" = "204" ]; then
  read_out="$(api GET "${TEST_PATH}")"; code
  if [ "${API_CODE}" = "200" ] && echo "${read_out}" | grep -q '"canary"'; then
    ok "app-token consegue escrever e ler em ${TEST_PATH}."
  else
    err "app-token não conseguiu ler de volta (HTTP ${API_CODE})."; exit 8
  fi
else
  err "app-token não conseguiu escrever em ${TEST_PATH} (HTTP ${API_CODE})."; exit 8
fi

export VAULT_TOKEN="${SAVED_ROOT}"

# ---------------------------------------------------------------------------
# 6. Sela o novo token no TPM (sem texto claro)
# ---------------------------------------------------------------------------
info "selando o app-token no TPM (app_token.enc)…"
APP_ENC="${TPM_DATA_DIR}/app_token.enc"
TMP_IN="$(mktemp /tmp/app-token.XXXXXX)"
printf '%s' "${APP_TOKEN}" > "${TMP_IN}"
seal_ok=0
if tpm2_create -C "${SRK_HANDLE}" -u "${APP_ENC}.pub" -r "${APP_ENC}.priv" \
     -i "${TMP_IN}" -Q --tcti "${TCTI}" 2>/dev/null; then
  printf 'TPM_SEALED_v2\n' > "${APP_ENC}"
  seal_ok=1
fi
rm -f "${TMP_IN}"
tpm2_flushcontext -t --tcti "${TCTI}" >/dev/null 2>&1 || true
if [ "${seal_ok}" -eq 1 ]; then
  ok "app-token selado no TPM -> ${APP_ENC} (recupere com get_root_token.sh apontando p/ este base)."
else
  err "falha ao selar o app-token no TPM — ABORTANDO antes de revogar o root."
  err "o token de menor privilégio existe no Vault, mas não foi persistido; nada foi revogado."
  exit 9
fi

# ---------------------------------------------------------------------------
# 7. Revoga o root token
# ---------------------------------------------------------------------------
if [ "${DRY_RUN}" -eq 1 ]; then
  warn "--dry-run: NÃO vou revogar o root token. Tudo o mais foi executado."
  ok "dry-run concluído: app-token criado, validado e selado no TPM."
  exit 0
fi

info "revogando o ROOT token (revoke-self)…"
export VAULT_TOKEN="${ROOT_TOKEN}"
api POST auth/token/revoke-self "" >/dev/null || true
# revoke-self responde 204; a partir daqui o root não deve mais funcionar.

# ---------------------------------------------------------------------------
# 8. Confirma que o root deixou de funcionar
# ---------------------------------------------------------------------------
info "confirmando que o root token foi revogado…"
out="$(api GET auth/token/lookup-self)"; code
if [ "${API_CODE}" = "403" ] || [ "${API_CODE}" = "400" ]; then
  ok "root token REVOGADO com sucesso (lookup-self -> HTTP ${API_CODE})."
else
  err "root token ainda parece válido (HTTP ${API_CODE}). Verifique manualmente!"
  exit 10
fi

echo
ok "Concluído: use o token de menor privilégio ('${APP_POLICY_NAME}') no lugar do root."
info "o app-token está selado em ${APP_ENC} (protegido pelo TPM deste host)."
warn "guarde as unseal keys/root apenas via TPM; para novo root use 'vault operator generate-root'."
