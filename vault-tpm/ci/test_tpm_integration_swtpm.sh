#!/usr/bin/env bash
#
# test_tpm_integration_swtpm.sh — Versão para CI/VM do test_tpm_integration.sh.
#
# O test_tpm_integration.sh original pressupõe:
#   - a stack docker-compose de pé (containers vault + tpm-validator);
#   - um TPM FÍSICO exposto como device (/dev/tpmrm0) dentro dos containers;
#   - um método de auth "tpm" habilitado no Vault (auth/tpm/roles) — que NÃO faz
#     parte do fluxo seal/unseal desta implementação.
#
# Nada disso está disponível num runner de CI (nem numa VM sem TPM físico). Este
# script cobre a PARTE aplicável do original — as operações de TPM (testes 1 e 2:
# operações básicas e de chaves) — usando o EMULADOR swtpm, sem docker-compose.
#
# Uso:
#   cd vault-tpm && ./ci/test_tpm_integration_swtpm.sh

set -euo pipefail

WORK_DIR="$(mktemp -d /tmp/tpm-integ.XXXXXX)"
TPM_STATE_DIR="${WORK_DIR}/mytpm"
TPM_SOCK="${WORK_DIR}/swtpm-sock"
SWTPM_LOG="${WORK_DIR}/swtpm.log"
export TPM2TOOLS_TCTI="swtpm:path=${TPM_SOCK}"

SWTPM_PID=""

if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YEL=$'\033[1;33m'; BLU=$'\033[0;34m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YEL=""; BLU=""; NC=""
fi
info(){ echo "${BLU}[INFO]${NC} $*"; }
ok(){ echo "${GREEN}[ OK ]${NC} $*"; }
warn(){ echo "${YEL}[WARN]${NC} $*"; }
fail(){ echo "${RED}[FAIL]${NC} $*"; }

cleanup() {
  local rc=$?
  [ -n "${SWTPM_PID}" ] && kill "${SWTPM_PID}" 2>/dev/null || true
  wait 2>/dev/null || true
  [ "${rc}" -ne 0 ] && { echo; warn "swtpm.log:"; cat "${SWTPM_LOG}" 2>/dev/null || true; }
  rm -rf "${WORK_DIR}" 2>/dev/null || true
  if [ "${rc}" -eq 0 ]; then echo; ok "INTEGRAÇÃO TPM (swtpm): OK."; else echo; fail "INTEGRAÇÃO TPM (swtpm) FALHOU (rc=${rc})."; fi
}
trap cleanup EXIT

require(){ command -v "$1" >/dev/null 2>&1 || { fail "dependência ausente: $1"; exit 3; }; }

STEP=0
step(){ STEP=$((STEP+1)); echo; echo "${BLU}=== $STEP. $* ===${NC}"; }

# ---------------------------------------------------------------------------
step "Pré-requisitos"
for b in swtpm tpm2_startup tpm2_getcap tpm2_pcrread tpm2_createprimary \
         tpm2_readpublic tpm2_create tpm2_sign tpm2_flushcontext; do require "$b"; done
ok "tpm2-tools + swtpm presentes."

# ---------------------------------------------------------------------------
step "Subindo swtpm (TPM 2.0 emulado)"
mkdir -p "${TPM_STATE_DIR}"
swtpm socket \
  --tpmstate "dir=${TPM_STATE_DIR}" --tpm2 \
  --ctrl "type=unixio,path=${TPM_SOCK}.ctrl" \
  --server "type=unixio,path=${TPM_SOCK}" \
  --flags not-need-init \
  --log "file=${SWTPM_LOG},level=1" &
SWTPM_PID=$!
for _ in $(seq 1 30); do [ -S "${TPM_SOCK}" ] && break; sleep 0.2; done
[ -S "${TPM_SOCK}" ] || { fail "socket do swtpm não apareceu"; exit 4; }
tpm2_startup -c >/dev/null 2>&1 || true
ok "swtpm no ar."

# ---------------------------------------------------------------------------
# Equivalente ao test_tpm_basic_operations() (teste 1 do original)
# ---------------------------------------------------------------------------
step "Operações básicas do TPM"
tpm2_getcap properties-fixed >/dev/null 2>&1 \
  && ok "TPM responde a properties-fixed." || { fail "properties-fixed falhou"; exit 5; }
tpm2_pcrread sha256:0 >/dev/null 2>&1 \
  && ok "leitura de PCR (sha256:0) OK." || { fail "tpm2_pcrread falhou"; exit 5; }
tpm2_getrandom 8 >/dev/null 2>&1 \
  && ok "tpm2_getrandom OK." || { fail "tpm2_getrandom falhou"; exit 5; }

# ---------------------------------------------------------------------------
# Equivalente ao test_tpm_key_operations() (teste 2 do original)
# ---------------------------------------------------------------------------
step "Operações com chaves TPM (createprimary / create / sign)"
cd "${WORK_DIR}"
tpm2_createprimary -c primary.ctx -Q
tpm2_readpublic -c primary.ctx >/dev/null
tpm2_flushcontext -t
ok "chave primária criada e lida."

echo "dados de teste" > test.txt
tpm2_create -C primary.ctx -G rsa -r key.prv -u key.pub -c key.ctx -Q 2>/dev/null || {
  # após flush o primário transiente precisa ser recarregado; recria e mantém carregado
  tpm2_createprimary -c primary.ctx -Q
  tpm2_create -C primary.ctx -G rsa -r key.prv -u key.pub -c key.ctx -Q
}
tpm2_sign -c key.ctx -g sha256 -o sig test.txt -Q
[ -s sig ] && ok "chave RSA criada e assinatura gerada." || { fail "assinatura vazia"; exit 6; }
tpm2_flushcontext -t

echo
ok "Todas as operações de TPM (básicas + chaves) passaram no emulador."
