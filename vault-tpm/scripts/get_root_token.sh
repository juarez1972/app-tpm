#!/usr/bin/env bash
#
# get_root_token.sh — Recupera o ROOT TOKEN inicial do Vault a partir do blob
# selado no TPM (root_token.enc), SEM gravar nada em disco e SEM deixar rastro
# nos logs dos containers.
#
# O token é selado por vault_initializer.py sob o SRK persistente do TPM.
# Este utilitário faz tpm2_load + tpm2_unseal e imprime o token no stdout
# (ou exporta em uma variável de ambiente, com a opção --export).
#
# IMPORTANTE:
#   - Só funciona no HOST que possui o TPM que selou o token (o segredo está
#     preso ao SRK persistente daquele TPM).
#   - Não escreve o token em arquivo. Se você redirecionar a saída para um
#     arquivo, a responsabilidade de protegê-lo passa a ser sua.
#
# Uso:
#   # imprime o token (cuidado com o histórico do shell / terminal)
#   ./scripts/get_root_token.sh
#
#   # carrega direto numa variável sem ecoar na tela:
#   export VAULT_TOKEN="$(./scripts/get_root_token.sh --quiet)"
#   vault status           # agora autenticado
#
#   # login interativo no Vault CLI sem expor o token no comando:
#   ./scripts/get_root_token.sh --quiet | vault login -
#
# Também recupera OUTROS tokens selados no mesmo esquema (ex.: o token de menor
# privilégio criado por revoke_root_token.sh) via TOKEN_BASENAME:
#   TOKEN_BASENAME=app_token ./scripts/get_root_token.sh --quiet
#
# Variáveis de ambiente (mesmas do initializer):
#   TPM_DATA_DIR    (default: ./tpm-data)
#   TPM2TOOLS_TCTI  (default: device:/dev/tpmrm0 ; use swtpm:path=... em VM/CI)
#   TPM_SRK_HANDLE  (default: 0x81010001)
#   TOKEN_BASENAME  (default: root_token ; base dos blobs .enc.pub/.enc.priv)

set -euo pipefail

TPM_DATA_DIR="${TPM_DATA_DIR:-./tpm-data}"
TCTI="${TPM2TOOLS_TCTI:-device:/dev/tpmrm0}"
SRK_HANDLE="${TPM_SRK_HANDLE:-0x81010001}"
TOKEN_BASENAME="${TOKEN_BASENAME:-root_token}"

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

PUB="${TPM_DATA_DIR}/${TOKEN_BASENAME}.enc.pub"
PRIV="${TPM_DATA_DIR}/${TOKEN_BASENAME}.enc.priv"

err() { echo "get_root_token: $*" >&2; }

command -v tpm2_load    >/dev/null 2>&1 || { err "tpm2-tools ausente"; exit 3; }
command -v tpm2_unseal  >/dev/null 2>&1 || { err "tpm2-tools ausente"; exit 3; }

if [ ! -f "${PUB}" ] || [ ! -f "${PRIV}" ]; then
  err "blobs do token não encontrados em ${TPM_DATA_DIR} (${TOKEN_BASENAME}.enc.pub/.priv)."
  err "o Vault já foi inicializado por vault_initializer.py neste host/TPM?"
  exit 4
fi

# Contexto temporário do objeto carregado; removido ao final.
CTX="$(mktemp /tmp/vault-root.XXXXXX.ctx)"
cleanup() {
  rm -f "${CTX}" 2>/dev/null || true
  # libera o objeto transiente carregado no TPM
  tpm2_flushcontext -t --tcti "${TCTI}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! tpm2_load -C "${SRK_HANDLE}" -u "${PUB}" -r "${PRIV}" -c "${CTX}" -Q --tcti "${TCTI}" 2>/dev/null; then
  err "tpm2_load falhou — o SRK em ${SRK_HANDLE} corresponde a este TPM?"
  exit 5
fi

# Imprime o token diretamente do TPM (stdout). Nada é gravado em disco.
if [ "${QUIET}" -eq 0 ]; then
  printf 'TOKEN (%s): ' "${TOKEN_BASENAME}"
fi
tpm2_unseal -c "${CTX}" --tcti "${TCTI}"
if [ "${QUIET}" -eq 0 ]; then
  echo
fi
exit 0
