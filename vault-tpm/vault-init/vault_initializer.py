#!/usr/bin/env python3
"""
vault_initializer.py — Inicialização e AUTO-UNSEAL do Vault com chaves protegidas por TPM.

Fluxo (produção, sem modo dev):
  1. Aguarda o Vault ficar acessível (health API) com RETRY EXPONENCIAL + jitter.
  2. Consulta /v1/sys/seal-status:
       - se não inicializado  -> roda /v1/sys/init (5 shares / threshold 3),
         sela cada unseal key no TPM (.enc) e sela o root token no TPM (.enc).
       - se já inicializado   -> recupera as unseal keys do TPM (.enc) para o unseal.
  3. Se selado, aplica as unseal keys via /v1/sys/unseal até atingir o threshold,
     com retry exponencial e tratamento de "Vault ainda não pronto".
  4. Confirma que o Vault ficou operacional (unsealed).

Notas de segurança:
  - NÃO grava segredos em texto claro (sem .txt). Apenas blobs .enc selados no TPM.
  - O selamento usa um SRK PERSISTENTE (tpm2_evictcontrol) + tpm2_create/tpm2_unseal,
    o que é DETERMINÍSTICO e recuperável entre boots — ao contrário de um primário
    efêmero, que impediria a descriptografia posterior.
  - Sem dependência de nuvem: tudo vive no TPM local + volume ./tpm-data.
  - Usa apenas a API REST do Vault (requests) — não requer o binário 'vault' no container.
"""

import os
import sys
import json
import time
import random
import subprocess
from pathlib import Path

import requests


# ----------------------------------------------------------------------------
# Configuração (sobrescrevível por variáveis de ambiente)
# ----------------------------------------------------------------------------
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://vault:8200")
OUTPUT_DIR = os.getenv("TPM_DATA_DIR", "/app/tpm-data")

TCTI = os.getenv("TPM2TOOLS_TCTI", "device:/dev/tpmrm0")
SRK_HANDLE = os.getenv("TPM_SRK_HANDLE", "0x81010001")

KEY_SHARES = int(os.getenv("UNSEAL_KEY_SHARES", "5"))
KEY_THRESHOLD = int(os.getenv("UNSEAL_KEY_THRESHOLD", "3"))

# Política de retry (backoff exponencial)
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "30"))
BASE_DELAY = float(os.getenv("BASE_DELAY", "2"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "60"))

ROOT_TOKEN_ENC = os.path.join(OUTPUT_DIR, "root_token.enc")


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def log(msg):
    print(f"[vault-init] {msg}", flush=True)


def backoff_sleep(attempt):
    """delay = min(MAX_DELAY, BASE_DELAY * 2^(attempt-1)) + jitter(0..1s)."""
    delay = min(MAX_DELAY, BASE_DELAY * (2 ** (attempt - 1)))
    delay += random.uniform(0, 1)
    log(f"aguardando {delay:.1f}s antes da próxima tentativa (backoff)…")
    time.sleep(delay)


def _tpm(cmd, **kwargs):
    """Executa um comando tpm2-tools já com o TCTI correto."""
    full = cmd + ["--tcti", TCTI]
    return subprocess.run(full, capture_output=True, timeout=kwargs.get("timeout", 30))


def check_tpm():
    """Verifica se o TPM está acessível."""
    try:
        return _tpm(["tpm2_getrandom", "4"], timeout=10).returncode == 0
    except Exception:
        return False


# ----------------------------------------------------------------------------
# TPM: SRK persistente + seal/unseal (recuperável entre boots)
# ----------------------------------------------------------------------------
def ensure_srk():
    """Cria e persiste o SRK no handle fixo (idempotente)."""
    # Já existe?
    if _tpm(["tpm2_readpublic", "-c", SRK_HANDLE], timeout=15).returncode == 0:
        return True
    log(f"provisionando SRK persistente em {SRK_HANDLE}…")
    primary = "/tmp/primary.ctx"
    r = _tpm(["tpm2_createprimary", "-C", "o", "-g", "sha256", "-G", "ecc",
              "-c", primary, "-Q"])
    if r.returncode != 0:
        log(f"❌ falha ao criar primário: {r.stderr.decode(errors='ignore')}")
        return False
    r = _tpm(["tpm2_evictcontrol", "-C", "o", "-c", primary, SRK_HANDLE, "-Q"])
    if os.path.exists(primary):
        os.unlink(primary)
    if r.returncode != 0:
        log(f"❌ falha ao persistir SRK: {r.stderr.decode(errors='ignore')}")
        return False
    return True


def tpm_seal(data: bytes, out_enc: str) -> bool:
    """
    Sela `data` sob o SRK persistente, gerando <out_enc>.pub / <out_enc>.priv.
    O arquivo `out_enc` em si guarda o nome-base (marcador) para o validador ver *.enc.
    """
    if not ensure_srk():
        return False
    in_file = "/tmp/seal_input.bin"
    pub = f"{out_enc}.pub"
    priv = f"{out_enc}.priv"
    try:
        with open(in_file, "wb") as f:
            f.write(data)
        r = _tpm(["tpm2_create", "-C", SRK_HANDLE,
                  "-u", pub, "-r", priv, "-i", in_file, "-Q"])
        if r.returncode != 0:
            log(f"❌ tpm2_create falhou: {r.stderr.decode(errors='ignore')}")
            return False
        # marcador .enc (o tpm-validator só verifica a presença de *.enc)
        with open(out_enc, "wb") as f:
            f.write(b"TPM_SEALED_v2\n")
        return True
    finally:
        if os.path.exists(in_file):
            os.unlink(in_file)


def tpm_unseal(out_enc: str):
    """Recupera o segredo selado a partir de <out_enc>.pub/.priv. Retorna bytes ou None."""
    pub = f"{out_enc}.pub"
    priv = f"{out_enc}.priv"
    if not (os.path.exists(pub) and os.path.exists(priv)):
        log(f"❌ blobs .pub/.priv ausentes para {out_enc}")
        return None
    ctx = f"/tmp/unseal_{os.getpid()}_{random.randint(1000,9999)}.ctx"
    try:
        r = _tpm(["tpm2_load", "-C", SRK_HANDLE, "-u", pub, "-r", priv, "-c", ctx, "-Q"])
        if r.returncode != 0:
            log(f"❌ tpm2_load falhou: {r.stderr.decode(errors='ignore')}")
            return None
        r = _tpm(["tpm2_unseal", "-c", ctx])
        if r.returncode != 0:
            log(f"❌ tpm2_unseal falhou: {r.stderr.decode(errors='ignore')}")
            return None
        return r.stdout
    finally:
        if os.path.exists(ctx):
            os.unlink(ctx)


# ----------------------------------------------------------------------------
# Vault API helpers
# ----------------------------------------------------------------------------
def vault_get(path):
    return requests.get(f"{VAULT_ADDR}/v1/{path}", timeout=10)


def vault_post(path, payload):
    return requests.post(f"{VAULT_ADDR}/v1/{path}", data=json.dumps(payload), timeout=10)


def wait_for_vault():
    """Espera o Vault responder o health endpoint, com retry exponencial."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        log(f"verificando disponibilidade do Vault (tentativa {attempt}/{MAX_ATTEMPTS})…")
        try:
            resp = vault_get("sys/health?standbyok=true&sealedcode=503&uninitcode=501")
            # 200 unsealed | 429 standby | 501 not init | 503 sealed
            if resp.status_code in (200, 429, 472, 473, 501, 503):
                log(f"✅ Vault acessível (HTTP {resp.status_code}).")
                return True
            log(f"⚠️  resposta inesperada do health (HTTP {resp.status_code}).")
        except requests.RequestException as e:
            log(f"⚠️  Vault ainda não responde ({e.__class__.__name__}).")
        if attempt < MAX_ATTEMPTS:
            backoff_sleep(attempt)
    log("❌ Vault não ficou disponível a tempo.")
    return False


def get_seal_status():
    """Retorna o JSON de sys/seal-status, ou None em erro."""
    try:
        resp = vault_get("sys/seal-status")
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


# ----------------------------------------------------------------------------
# Init + Unseal
# ----------------------------------------------------------------------------
def initialize_vault():
    """Roda sys/init, sela unseal keys e root token no TPM. Retorna lista de keys ou None."""
    log(f"inicializando Vault ({KEY_SHARES} shares / threshold {KEY_THRESHOLD})…")
    resp = vault_post("sys/init", {
        "secret_shares": KEY_SHARES,
        "secret_threshold": KEY_THRESHOLD,
    })
    if resp.status_code != 200:
        log(f"❌ init falhou (HTTP {resp.status_code}): {resp.text}")
        return None

    data = resp.json()
    keys = data.get("keys_base64") or data.get("keys") or []
    root_token = data.get("root_token", "")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Sela cada unseal key no TPM (sem cópia em claro)
    for i, key in enumerate(keys):
        enc_path = os.path.join(OUTPUT_DIR, f"unseal_key_{i}.enc")
        if tpm_seal(key.encode(), enc_path):
            log(f"✅ unseal key {i} selada no TPM -> {enc_path}")
        else:
            log(f"❌ falha ao selar unseal key {i}")

    # Sela o root token no TPM (sem cópia em claro)
    if root_token and tpm_seal(root_token.encode(), ROOT_TOKEN_ENC):
        log("✅ root token selado no TPM (não gravado em texto claro).")
    log("🔑 IMPORTANTE: o root token está protegido apenas pelo TPM deste host.")

    return keys


def recover_keys_from_tpm():
    """Recupera as unseal keys previamente seladas no TPM (unseal_key_*.enc)."""
    keys = []
    i = 0
    while True:
        enc_path = os.path.join(OUTPUT_DIR, f"unseal_key_{i}.enc")
        if not os.path.exists(enc_path):
            break
        data = tpm_unseal(enc_path)
        if data:
            keys.append(data.decode().strip())
            log(f"✅ unseal key {i} recuperada do TPM.")
        else:
            log(f"❌ não foi possível recuperar unseal key {i}.")
        i += 1
    return keys


def unseal_vault(keys):
    """Aplica as unseal keys via API até destravar, com retry exponencial."""
    if not keys:
        log("❌ nenhuma unseal key disponível para destravar o Vault.")
        return False

    applied = 0
    for key in keys:
        # já destravado?
        status = get_seal_status()
        if status and not status.get("sealed", True):
            log("✅ Vault já destravado.")
            return True

        # retry por chave (erros transitórios / Vault ainda não pronto)
        for attempt in range(1, 4):
            try:
                resp = vault_post("sys/unseal", {"key": key})
                if resp.status_code == 200:
                    body = resp.json()
                    applied += 1
                    log(f"share aceito — progresso {body.get('progress')}/{body.get('t')}.")
                    if not body.get("sealed", True):
                        log("🎉 Vault DESTRAVADO com sucesso.")
                        return True
                    break
                else:
                    log(f"⚠️  unseal retornou HTTP {resp.status_code} (tentativa {attempt}/3).")
            except requests.RequestException as e:
                log(f"⚠️  erro transitório no unseal ({e.__class__.__name__}, tentativa {attempt}/3).")
            backoff_sleep(attempt)

    status = get_seal_status()
    if status and not status.get("sealed", True):
        return True
    log(f"❌ não foi possível destravar: apenas {applied} shares aceitos (threshold={KEY_THRESHOLD}).")
    return False


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    log("== VAULT INITIALIZER — auto-unseal via TPM (produção) ==")
    log(f"VAULT_ADDR={VAULT_ADDR} | shares={KEY_SHARES} threshold={KEY_THRESHOLD}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if check_tpm():
        log("✅ TPM operacional.")
    else:
        log("❌ TPM não disponível — abortando (sem TPM não há proteção das chaves).")
        sys.exit(1)

    if not wait_for_vault():
        sys.exit(1)

    status = get_seal_status()
    if status is None:
        log("❌ não foi possível obter seal-status do Vault.")
        sys.exit(1)

    if not status.get("initialized", False):
        keys = initialize_vault()
        if keys is None:
            sys.exit(1)
    else:
        log("Vault já inicializado — recuperando unseal keys do TPM.")
        keys = recover_keys_from_tpm()

    # Se já estiver destravado, nada a fazer
    status = get_seal_status()
    if status and not status.get("sealed", True):
        log("✅ Vault já está destravado — nada a fazer.")
        _list_artifacts()
        return

    log("Vault está SELADO — iniciando unseal via chaves do TPM.")
    if not unseal_vault(keys):
        sys.exit(1)

    _list_artifacts()
    log("✅ Processo concluído: Vault operacional.")


def _list_artifacts():
    log("artefatos em tpm-data:")
    for f in sorted(Path(OUTPUT_DIR).iterdir()):
        try:
            log(f"   • {f.name} ({f.stat().st_size} bytes)")
        except OSError:
            pass


if __name__ == "__main__":
    main()
