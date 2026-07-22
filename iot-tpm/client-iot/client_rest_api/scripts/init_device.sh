#!/usr/bin/env bash
#
# init_device.sh — Inicialização/provisionamento de um dispositivo IoT (IoT-TPM)
#
# Faz, de ponta a ponta, o provisionamento de um dispositivo (REST ou MQTT):
#   1. Verifica o TPM.
#   2. Garante um SRK persistente (mesma convenção do projeto vault-tpm: 0x81010001).
#   3. Gera (ou reutiliza) um segredo TOTP Base32 do dispositivo — só em RAM.
#   4. Sela o segredo no TPM do dispositivo:
#        <TPM_DATA_DIR>/<DEVICE_ID>_otp.enc.pub / .priv
#   5. (Opcional) Registra o mesmo segredo no Vault do servidor, no path
#        secret/data/<VAULT_DEVICE_BASE>/<DEVICE_ID>  (campo 'otp_secret'),
#      para que o servidor (REST ou MQTT) valide o TOTP do dispositivo.
#
# O segredo em texto claro NUNCA é gravado em disco: fica apenas em variável de
# shell e é passado ao tpm2_create/curl via stdin.
#
# Uso:
#   DEVICE_ID=device-001 ./scripts/init_device.sh
#   DEVICE_ID=device-001 VAULT_ADDR=http://192.168.56.106:8200 \
#     VAULT_TOKEN=<app_token> ./scripts/init_device.sh
#
# Variáveis de ambiente:
#   DEVICE_ID          (default: device-001)   ID lógico do dispositivo
#   TPM_DATA_DIR       (default: ./tpm-data)    onde ficam os blobs selados
#   TPM_SRK_HANDLE     (default: 0x81010001)    handle do SRK persistente
#   TPM2TOOLS_TCTI     (default: device:/dev/tpmrm0)
#   OTP_SECRET         (opcional)               reutiliza um segredo já existente
#   REGISTER_IN_VAULT  (default: auto)          auto|yes|no — registrar no Vault
#   VAULT_ADDR         (default: http://127.0.0.1:8200)
#   VAULT_TOKEN        (necessário p/ registrar no Vault; ex.: app_token do TPM)
#   VAULT_KV_MOUNT     (default: secret)
#   VAULT_DEVICE_BASE  (default: tpm-verified/iot/devices)
#   VAULT_SECRET_FIELD (default: otp_secret)
#
# Códigos de saída: 0 ok | 1 erro de uso/deps | 2 falha de TPM | 3 falha de Vault
set -euo pipefail

DEVICE_ID="${DEVICE_ID:-device-001}"
TPM_DATA_DIR="${TPM_DATA_DIR:-./tpm-data}"
SRK_HANDLE="${TPM_SRK_HANDLE:-0x81010001}"
TCTI="${TPM2TOOLS_TCTI:-device:/dev/tpmrm0}"
REGISTER_IN_VAULT="${REGISTER_IN_VAULT:-auto}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
VAULT_KV_MOUNT="${VAULT_KV_MOUNT:-secret}"
VAULT_DEVICE_BASE="${VAULT_DEVICE_BASE:-tpm-verified/iot/devices}"
VAULT_SECRET_FIELD="${VAULT_SECRET_FIELD:-otp_secret}"

export TPM2TOOLS_TCTI="${TCTI}"

info() { printf '\033[36m[init]\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m[ ok ]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[erro]\033[0m %s\n' "$*" >&2; }

# ── 1. Dependências e TPM ─────────────────────────────────────────────────────
for b in tpm2_getrandom tpm2_createprimary tpm2_evictcontrol tpm2_create tpm2_flushcontext; do
  command -v "$b" >/dev/null 2>&1 || { err "tpm2-tools ausente ($b)"; exit 1; }
done
command -v python3 >/dev/null 2>&1 || { err "python3 ausente"; exit 1; }

info "verificando TPM (TCTI=${TCTI})…"
if ! tpm2_getrandom 4 >/dev/null 2>&1; then
  err "TPM não acessível. Verifique /dev/tpmrm0 ou use swtpm."
  exit 2
fi
ok "TPM acessível."

mkdir -p "${TPM_DATA_DIR}"

# ── 2. SRK persistente (idempotente) ──────────────────────────────────────────
info "garantindo SRK persistente em ${SRK_HANDLE}…"
if tpm2_readpublic -c "${SRK_HANDLE}" >/dev/null 2>&1; then
  ok "SRK já existe em ${SRK_HANDLE}."
else
  PRIMARY_CTX="$(mktemp --suffix=.ctx)"
  trap 'rm -f "${PRIMARY_CTX}"' EXIT
  tpm2_createprimary -C o -g sha256 -G ecc -c "${PRIMARY_CTX}" -Q
  tpm2_evictcontrol -C o -c "${PRIMARY_CTX}" "${SRK_HANDLE}" -Q
  rm -f "${PRIMARY_CTX}"; trap - EXIT
  ok "SRK criado e tornado persistente em ${SRK_HANDLE}."
fi
tpm2_flushcontext -t >/dev/null 2>&1 || true

# ── 3. Segredo TOTP (Base32) — apenas em RAM ──────────────────────────────────
if [ -n "${OTP_SECRET:-}" ]; then
  SECRET="${OTP_SECRET}"
  info "reutilizando OTP_SECRET fornecido via ambiente."
else
  SECRET="$(python3 -c 'import pyotp; print(pyotp.random_base32())')"
  info "novo segredo TOTP gerado para '${DEVICE_ID}'."
fi

# ── 4. Selar o segredo no TPM ─────────────────────────────────────────────────
PUB="${TPM_DATA_DIR}/${DEVICE_ID}_otp.enc.pub"
PRIV="${TPM_DATA_DIR}/${DEVICE_ID}_otp.enc.priv"

info "selando o segredo no TPM…"
# -i - lê o input do stdin (o segredo nunca toca o disco em texto claro)
if printf '%s' "${SECRET}" | tpm2_create -C "${SRK_HANDLE}" \
      -u "${PUB}" -r "${PRIV}" -i - -Q; then
  ok "segredo selado em ${PUB} / ${PRIV}."
else
  err "tpm2_create falhou ao selar o segredo."
  exit 2
fi
tpm2_flushcontext -t >/dev/null 2>&1 || true

# ── 5. Registrar no Vault do servidor (opcional) ──────────────────────────────
do_vault="no"
case "${REGISTER_IN_VAULT}" in
  yes)  do_vault="yes" ;;
  no)   do_vault="no"  ;;
  auto) [ -n "${VAULT_TOKEN}" ] && do_vault="yes" || do_vault="no" ;;
  *)    err "REGISTER_IN_VAULT inválido: ${REGISTER_IN_VAULT}"; exit 1 ;;
esac

if [ "${do_vault}" = "yes" ]; then
  if [ -z "${VAULT_TOKEN}" ]; then
    err "VAULT_TOKEN necessário para registrar no Vault."
    exit 3
  fi
  command -v curl >/dev/null 2>&1 || { err "curl ausente"; exit 1; }
  VPATH="${VAULT_KV_MOUNT}/data/${VAULT_DEVICE_BASE}/${DEVICE_ID}"
  info "registrando segredo no Vault em ${VPATH}…"
  # payload montado em Python para escapar corretamente; segredo via env, não CLI
  payload="$(OTP_SECRET="${SECRET}" FIELD="${VAULT_SECRET_FIELD}" DEV="${DEVICE_ID}" \
    python3 -c 'import json,os; print(json.dumps({"data":{os.environ["FIELD"]:os.environ["OTP_SECRET"],"device_id":os.environ["DEV"]}}))')"
  code="$(printf '%s' "${payload}" | curl -s -o /tmp/vault_resp.$$ -w '%{http_code}' \
      -H "X-Vault-Token: ${VAULT_TOKEN}" \
      -H "Content-Type: application/json" \
      --data @- "${VAULT_ADDR}/v1/${VPATH}")" || true
  if [ "${code}" = "200" ] || [ "${code}" = "204" ]; then
    ok "segredo registrado no Vault (HTTP ${code})."
  else
    err "falha ao registrar no Vault (HTTP ${code}). Resposta:"
    cat /tmp/vault_resp.$$ >&2 2>/dev/null || true
    rm -f /tmp/vault_resp.$$
    exit 3
  fi
  rm -f /tmp/vault_resp.$$
else
  info "registro no Vault pulado (REGISTER_IN_VAULT=${REGISTER_IN_VAULT})."
  echo
  info "Registre manualmente o segredo no servidor, por exemplo:"
  echo "  vault kv put ${VAULT_KV_MOUNT}/${VAULT_DEVICE_BASE}/${DEVICE_ID} ${VAULT_SECRET_FIELD}=<SEGREDO>"
fi

# Limpa o segredo da memória do shell
SECRET=""

echo
ok "Dispositivo '${DEVICE_ID}' provisionado."
info "Próximo passo: suba o cliente (o segredo será recuperado do TPM):"
echo "  DEVICE_ID=${DEVICE_ID} python3 client_iot.py       # cliente REST"
echo "  DEVICE_ID=${DEVICE_ID} python3 client_mqtt.py      # cliente MQTT"
exit 0
