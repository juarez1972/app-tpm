#!/usr/bin/env bash
set -euo pipefail

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8201}"
TPM_DIR="${TPM_DIR:-./tpm-data}"
VAULT_CONTAINER="${VAULT_CONTAINER:-vault}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Erro: comando ausente: $1" >&2; exit 1; }
}

require_cmd docker
require_cmd jq
require_cmd tpm2_createprimary
require_cmd tpm2_create
require_cmd tpm2_load
require_cmd tpm2_rsaencrypt
require_cmd tpm2_rsadecrypt
require_cmd xxd
require_cmd vault

mkdir -p "$TPM_DIR"

status_json="$(vault status -format=json)"
initialized="$(echo "$status_json" | jq -r '.initialized')"
sealed="$(echo "$status_json" | jq -r '.sealed')"

if [[ "$initialized" != "false" ]]; then
  echo "Vault já está inicializado. Abortando para evitar sobrescrita lógica." >&2
  exit 1
fi

init_json="$(vault operator init -format=json -key-shares=1 -key-threshold=1)"
echo "$init_json" > "$TMP_DIR/init.json"

root_token="$(echo "$init_json" | jq -r '.root_token')"
unseal_key="$(echo "$init_json" | jq -r '.unseal_keys_b64[0]')"

printf '%s' "$unseal_key" > "$TPM_DIR/unseal_key.b64"
printf '%s' "$root_token" > "$TMP_DIR/root-token.txt"

vault operator unseal "$unseal_key" >/dev/null

if [[ ! -f "$TPM_DIR/primary.ctx" ]]; then
  tpm2_createprimary -C o -g sha256 -G rsa -c "$TPM_DIR/primary.ctx" >/dev/null
fi

if [[ ! -f "$TPM_DIR/rootwrap.pub" || ! -f "$TPM_DIR/rootwrap.priv" ]]; then
  tpm2_create -C "$TPM_DIR/primary.ctx" -G rsa -u "$TPM_DIR/rootwrap.pub" -r "$TPM_DIR/rootwrap.priv" >/dev/null
fi

if [[ ! -f "$TPM_DIR/rootwrap.ctx" ]]; then
  tpm2_load -C "$TPM_DIR/primary.ctx" -u "$TPM_DIR/rootwrap.pub" -r "$TPM_DIR/rootwrap.priv" -c "$TPM_DIR/rootwrap.ctx" >/dev/null
fi

tpm2_rsaencrypt -c "$TPM_DIR/rootwrap.ctx" -o "$TPM_DIR/root_token.enc" "$TMP_DIR/root-token.txt"
shred -u "$TMP_DIR/root-token.txt"

vault login "$root_token" >/dev/null
vault token create -policy=root -ttl=24h -format=json > "$TPM_DIR/bootstrap_admin_token.json"

cat > "$TPM_DIR/RECOVERY_INFO.txt" <<EOF
Vault inicializado com sucesso.

Arquivos gerados:
- unseal_key.b64               -> chave de unseal (guardar em local seguro; idealmente mover para processo mais robusto)
- root_token.enc              -> root token cifrado com chave RSA protegida no TPM
- primary.ctx/rootwrap.*      -> material de contexto TPM local
- bootstrap_admin_token.json  -> token administrativo temporário de bootstrap

ATENÇÃO:
- O root token em claro foi apagado do disco temporário.
- O arquivo bootstrap_admin_token.json contém segredo em claro e deve ser removido após uso.
- Em produção real, habilite TLS e prefira políticas mínimas em vez de policy=root para operação diária.
EOF

echo "Vault inicializado, unsealed e root token protegido no TPM em $TPM_DIR/root_token.enc"
