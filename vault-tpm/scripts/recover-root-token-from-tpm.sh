#!/usr/bin/env bash
set -euo pipefail

TPM_DIR="${TPM_DIR:-./tpm-data}"
OUT_FILE="${OUT_FILE:-}"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Erro: comando ausente: $1" >&2; exit 1; }
}

require_cmd tpm2_rsadecrypt

for f in "$TPM_DIR/rootwrap.ctx" "$TPM_DIR/root_token.enc"; do
  [[ -f "$f" ]] || { echo "Erro: arquivo ausente: $f" >&2; exit 1; }
done

tpm2_rsadecrypt -c "$TPM_DIR/rootwrap.ctx" -o "$TMP_FILE" "$TPM_DIR/root_token.enc" >/dev/null

if [[ -n "$OUT_FILE" ]]; then
  install -m 600 "$TMP_FILE" "$OUT_FILE"
  echo "Token recuperado em $OUT_FILE"
else
  cat "$TMP_FILE"
fi
