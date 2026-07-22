#!/usr/bin/env bash
#
# test_seal_unseal.sh — Teste de CI do fluxo seal/unseal do vault-tpm usando swtpm.
#
# Este teste NÃO exige um TPM físico: usa o emulador swtpm exposto via TCTI.
# Ele exercita o MESMO vault_initializer.py usado em produção, apontando
# TPM2TOOLS_TCTI para o emulador, e valida ponta a ponta:
#
#   1. TPM (emulado) operacional (tpm2_getrandom).
#   2. Vault REAL (server mode) sobe SELADO e NÃO inicializado.
#   3. vault_initializer.py roda sys/init (5/3), sela as chaves + root token no TPM
#      e destrava o Vault (auto-unseal) — gerando *.enc / *.pub / *.priv.
#   4. NENHUM segredo em texto claro (sem *.txt em tpm-data).
#   5. RECUPERAÇÃO ENTRE BOOTS: reinicia o Vault SELADO (sem reinicializar) e roda
#      o initializer de novo — ele deve RECUPERAR as chaves do TPM e destravar,
#      provando que o SRK persistente funciona entre reinícios.
#
# Uso local (Linux com swtpm, tpm2-tools, python3, e o binário 'vault'):
#   cd vault-tpm && ./ci/test_seal_unseal.sh
#
# No CI, o workflow .github/workflows/ci-seal-unseal.yml instala as dependências.

set -euo pipefail

# ---------------------------------------------------------------------------
# Localização e ambiente
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INITIALIZER="${PROJECT_DIR}/vault-init/vault_initializer.py"

WORK_DIR="$(mktemp -d /tmp/vault-tpm-ci.XXXXXX)"
TPM_STATE_DIR="${WORK_DIR}/mytpm"
TPM_SOCK="${WORK_DIR}/swtpm-sock"
TPM_DATA_DIR="${WORK_DIR}/tpm-data"
VAULT_FILE_DIR="${WORK_DIR}/vault-file"
VAULT_LOG="${WORK_DIR}/vault.log"
SWTPM_LOG="${WORK_DIR}/swtpm.log"

# Vault
export VAULT_ADDR="http://127.0.0.1:8200"
VAULT_CONFIG="${WORK_DIR}/vault-config.hcl"

# Config repassada ao initializer (mesmas variáveis usadas em produção)
export TPM2TOOLS_TCTI="swtpm:path=${TPM_SOCK}"
export TPM_DATA_DIR
export TPM_SRK_HANDLE="0x81010001"
export UNSEAL_KEY_SHARES="5"
export UNSEAL_KEY_THRESHOLD="3"
# Backoff curto para o CI ser rápido
export MAX_ATTEMPTS="20"
export BASE_DELAY="1"
export MAX_DELAY="4"

SWTPM_PID=""
VAULT_PID=""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YEL=$'\033[1;33m'; BLU=$'\033[0;34m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YEL=""; BLU=""; NC=""
fi
info()  { echo "${BLU}[INFO]${NC} $*"; }
ok()    { echo "${GREEN}[ OK ]${NC} $*"; }
warn()  { echo "${YEL}[WARN]${NC} $*"; }
fail()  { echo "${RED}[FAIL]${NC} $*"; }

STEP=0
step() { STEP=$((STEP+1)); echo; echo "${BLU}=== Passo ${STEP}: $* ===${NC}"; }

# ---------------------------------------------------------------------------
# Limpeza
# ---------------------------------------------------------------------------
cleanup() {
  local rc=$?
  info "limpando (rc=${rc})…"
  [ -n "${VAULT_PID}" ] && kill "${VAULT_PID}" 2>/dev/null || true
  [ -n "${SWTPM_PID}" ] && kill "${SWTPM_PID}" 2>/dev/null || true
  wait 2>/dev/null || true
  if [ "${rc}" -ne 0 ]; then
    echo; warn "===== vault.log (últimas 40 linhas) ====="; tail -n 40 "${VAULT_LOG}" 2>/dev/null || true
    echo; warn "===== swtpm.log ====="; cat "${SWTPM_LOG}" 2>/dev/null || true
  fi
  rm -rf "${WORK_DIR}" 2>/dev/null || true
  if [ "${rc}" -eq 0 ]; then echo; ok "TESTE CONCLUÍDO COM SUCESSO."; else echo; fail "TESTE FALHOU (rc=${rc})."; fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Pré-requisitos
# ---------------------------------------------------------------------------
require() { command -v "$1" >/dev/null 2>&1 || { fail "dependência ausente: $1"; exit 3; }; }

check_prereqs() {
  step "Verificando pré-requisitos"
  for bin in swtpm tpm2_startup tpm2_getrandom vault python3; do require "$bin"; done
  python3 -c "import requests" 2>/dev/null || { fail "módulo python 'requests' ausente (pip install requests)"; exit 3; }
  [ -f "${INITIALIZER}" ] || { fail "não encontrei ${INITIALIZER}"; exit 3; }
  ok "todas as dependências presentes."
}

# ---------------------------------------------------------------------------
# swtpm (TPM emulado)
# ---------------------------------------------------------------------------
start_swtpm() {
  step "Subindo swtpm (TPM 2.0 emulado)"
  mkdir -p "${TPM_STATE_DIR}"
  swtpm socket \
    --tpmstate "dir=${TPM_STATE_DIR}" \
    --tpm2 \
    --ctrl "type=unixio,path=${TPM_SOCK}.ctrl" \
    --server "type=unixio,path=${TPM_SOCK}" \
    --flags not-need-init \
    --log "file=${SWTPM_LOG},level=1" \
    &
  SWTPM_PID=$!

  # Espera o socket aparecer
  for _ in $(seq 1 30); do [ -S "${TPM_SOCK}" ] && break; sleep 0.2; done
  [ -S "${TPM_SOCK}" ] || { fail "socket do swtpm não apareceu"; exit 4; }

  # Inicializa o TPM (startup) e valida acesso
  tpm2_startup -c --tcti "swtpm:path=${TPM_SOCK}" >/dev/null 2>&1 || true
  if tpm2_getrandom 8 --tcti "swtpm:path=${TPM_SOCK}" >/dev/null 2>&1; then
    ok "swtpm operacional (tpm2_getrandom respondeu)."
  else
    fail "swtpm não respondeu a tpm2_getrandom."; exit 4
  fi
}

# ---------------------------------------------------------------------------
# Vault real (server mode, storage file)
# ---------------------------------------------------------------------------
write_vault_config() {
  cat > "${VAULT_CONFIG}" <<EOF
ui = false
disable_mlock = true
listener "tcp" {
  address     = "127.0.0.1:8200"
  tls_disable = 1
}
storage "file" {
  path = "${VAULT_FILE_DIR}"
}
api_addr = "${VAULT_ADDR}"
EOF
}

start_vault() {
  step "Subindo Vault real (server mode, storage file)"
  mkdir -p "${VAULT_FILE_DIR}" "${TPM_DATA_DIR}"
  write_vault_config
  vault server -config="${VAULT_CONFIG}" > "${VAULT_LOG}" 2>&1 &
  VAULT_PID=$!

  # Espera o health responder (sealed=503 / uninit=501 são respostas válidas)
  for _ in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' \
      "${VAULT_ADDR}/v1/sys/health?sealedcode=503&uninitcode=501" 2>/dev/null || echo 000)"
    case "${code}" in 200|429|501|503) ok "Vault respondendo (HTTP ${code})."; return 0;; esac
    sleep 0.5
  done
  fail "Vault não respondeu ao health a tempo."; exit 5
}

# Reinicia o processo do Vault SEM apagar o storage (simula um novo boot -> selado)
restart_vault_sealed() {
  info "reiniciando o processo do Vault (novo boot -> deve voltar SELADO)…"
  kill "${VAULT_PID}" 2>/dev/null || true
  wait "${VAULT_PID}" 2>/dev/null || true
  vault server -config="${VAULT_CONFIG}" > "${VAULT_LOG}" 2>&1 &
  VAULT_PID=$!
  for _ in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' \
      "${VAULT_ADDR}/v1/sys/health?sealedcode=503&uninitcode=501" 2>/dev/null || echo 000)"
    case "${code}" in 200|429|501|503) return 0;; esac
    sleep 0.5
  done
  fail "Vault não voltou após restart."; exit 5
}

# ---------------------------------------------------------------------------
# Helpers de asserção
# ---------------------------------------------------------------------------
seal_status_field() {  # $1 = campo json (ex.: sealed / initialized)
  curl -s "${VAULT_ADDR}/v1/sys/seal-status" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('$1'))"
}

assert_sealed()   { [ "$(seal_status_field sealed)" = "True" ]      || { fail "esperava sealed=True";      exit 6; }; }
assert_unsealed() { [ "$(seal_status_field sealed)" = "False" ]     || { fail "esperava sealed=False";     exit 6; }; }
assert_uninit()   { [ "$(seal_status_field initialized)" = "False" ]|| { fail "esperava initialized=False";exit 6; }; }
assert_init()     { [ "$(seal_status_field initialized)" = "True" ] || { fail "esperava initialized=True"; exit 6; }; }

run_initializer() { python3 "${INITIALIZER}"; }

# ---------------------------------------------------------------------------
# Fluxo do teste
# ---------------------------------------------------------------------------
main() {
  check_prereqs
  start_swtpm
  start_vault

  step "Estado inicial: Vault SELADO e NÃO inicializado"
  assert_uninit; assert_sealed
  ok "Vault está uninitialized + sealed, como esperado."

  step "1ª execução do initializer: init real + seal no TPM + auto-unseal"
  run_initializer
  assert_init
  assert_unsealed
  ok "Vault inicializado e DESTRAVADO pela 1ª execução."

  step "Verificando artefatos selados no TPM (sem texto claro)"
  ls -la "${TPM_DATA_DIR}"
  enc_count="$(find "${TPM_DATA_DIR}" -maxdepth 1 -name 'unseal_key_*.enc' | wc -l | tr -d ' ')"
  [ "${enc_count}" -eq "${UNSEAL_KEY_SHARES}" ] \
    || { fail "esperava ${UNSEAL_KEY_SHARES} arquivos unseal_key_*.enc, achei ${enc_count}"; exit 7; }
  ok "encontrados ${enc_count} unseal_key_*.enc."

  # O initializer gera o marcador <base>.enc e os blobs TPM <base>.enc.pub / <base>.enc.priv
  for f in \
    "unseal_key_0.enc" "unseal_key_0.enc.pub" "unseal_key_0.enc.priv" \
    "root_token.enc" "root_token.enc.pub" "root_token.enc.priv"; do
    [ -f "${TPM_DATA_DIR}/${f}" ] || { fail "faltando ${f}"; exit 7; }
  done
  ok "blobs .enc + .enc.pub/.enc.priv presentes (unseal keys + root token)."

  step "Garantindo que NÃO há segredos em texto claro"
  txt_count="$(find "${TPM_DATA_DIR}" -maxdepth 1 -name '*.txt' | wc -l | tr -d ' ')"
  [ "${txt_count}" -eq 0 ] || { fail "encontrei ${txt_count} arquivo(s) .txt em tpm-data"; find "${TPM_DATA_DIR}" -name '*.txt'; exit 8; }
  # O SRK persistente deve existir no TPM
  tpm2_readpublic -c "${TPM_SRK_HANDLE}" --tcti "${TPM2TOOLS_TCTI}" >/dev/null 2>&1 \
    && ok "SRK persistente presente em ${TPM_SRK_HANDLE}." \
    || { fail "SRK persistente não encontrado em ${TPM_SRK_HANDLE}"; exit 8; }
  ok "nenhum segredo em texto claro."

  step "Idempotência: 2ª execução com Vault JÁ destravado (não deve quebrar)"
  run_initializer
  assert_unsealed
  ok "2ª execução tratou 'já destravado' sem erro."

  step "RECUPERAÇÃO ENTRE BOOTS: reinicia Vault selado e reunsea SÓ com chaves do TPM"
  restart_vault_sealed
  assert_init      # continua inicializado (storage preservado)
  assert_sealed    # mas voltou selado (novo boot)
  ok "após restart: initialized=True, sealed=True (novo boot simulado)."

  info "rodando initializer novamente — deve RECUPERAR chaves do TPM e destravar…"
  run_initializer
  assert_unsealed
  ok "Vault DESTRAVADO usando apenas as chaves recuperadas do TPM (SRK persistente OK)."

  echo
  ok "Todas as asserções passaram: init real + seal/unseal + recuperação entre boots."
}

main "$@"
