"""
Cliente REST API — dispositivo IoT (IoT-TPM)

Autentica-se periodicamente no servidor via HTTP + TOTP. O segredo TOTP fica
SELADO no TPM do dispositivo e é recuperado apenas em memória (nunca gravado em
disco em texto claro). Em modo de desenvolvimento, aceita OTP_SECRET via .env.

Fluxo:
  1. POST {API_URL}/login  {"device_id": ...}          -> session_token
  2. Loop: POST {API_URL}/verify {"session_token", "otp_code"} a cada OTP_INTERVAL

Recuperação do segredo (mesma convenção do projeto vault-tpm / par MQTT):
  - SRK persistente:            TPM_SRK_HANDLE (default 0x81010001)
  - Blobs selados (por device): <TPM_DATA_DIR>/<device_id>_otp.enc.pub / .priv
  - Recuperação:                tpm2_load + tpm2_unseal (saída só para stdout/RAM)

O provisionamento (gerar o segredo, registrar no Vault do servidor e selar no
TPM do cliente) é feito por scripts/init_device.sh — veja o README (Seção 6).

IMPORTANTE: OTP_INTERVAL deve ser idêntico ao do servidor.
"""

import os
import sys
import time
import subprocess
import tempfile

import requests
import pyotp
from dotenv import load_dotenv

from crypto_envelope import seal_otp

load_dotenv()

# ── Configuração ──────────────────────────────────────────────────────────────
DEVICE_ID    = os.getenv("DEVICE_ID", "device-001")
API_URL      = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
OTP_INTERVAL = int(os.getenv("OTP_INTERVAL", "60"))
# Modo de envio do OTP: 'hmac' (envelope HMAC, default) ou 'plain' (legado).
# Em 'hmac' o código nunca trafega em claro — só o HMAC-SHA256(seed, otp|nonce|ts).
OTP_MODE     = os.getenv("OTP_MODE", "hmac").strip().lower()
CA_CERT      = os.getenv("CA_CERT")  # opcional — verifica TLS do servidor se definido

# Credenciais estáticas OPCIONAIS (só usadas se o servidor as exigir)
API_USER = os.getenv("API_USER")
API_PASS = os.getenv("API_PASS")

# TPM
TPM_DATA_DIR   = os.getenv("TPM_DATA_DIR", "./tpm-data")
TPM_SRK_HANDLE = os.getenv("TPM_SRK_HANDLE", "0x81010001")
TPM2TOOLS_TCTI = os.getenv("TPM2TOOLS_TCTI", "device:/dev/tpmrm0")

# Fallback de desenvolvimento (sem TPM)
FALLBACK_OTP_SECRET = os.getenv("OTP_SECRET")

# verify= do requests: True (default), caminho da CA, ou False (dev)
_VERIFY = CA_CERT if (CA_CERT and os.path.isfile(CA_CERT)) else (
    False if API_URL.startswith("http://") else True
)


def _tpm_env() -> dict:
    env = os.environ.copy()
    env["TPM2TOOLS_TCTI"] = TPM2TOOLS_TCTI
    return env


def check_tpm() -> bool:
    """Verifica se o TPM está presente e funcional."""
    try:
        subprocess.run(
            ["tpm2_getrandom", "4"],
            capture_output=True, check=True, env=_tpm_env(),
        )
        return True
    except Exception:
        return False


def unseal_otp_secret() -> str | None:
    """
    Recupera o segredo TOTP selado no TPM, retornando-o apenas em memória.
    Blobs esperados: <TPM_DATA_DIR>/<DEVICE_ID>_otp.enc.pub / .priv
    Nunca grava o segredo em texto claro no disco.
    """
    pub  = os.path.join(TPM_DATA_DIR, f"{DEVICE_ID}_otp.enc.pub")
    priv = os.path.join(TPM_DATA_DIR, f"{DEVICE_ID}_otp.enc.priv")

    if not (os.path.isfile(pub) and os.path.isfile(priv)):
        print(f"[TPM] Blobs selados não encontrados para '{DEVICE_ID}':")
        print(f"      esperado: {pub} / {priv}")
        print("      Rode scripts/init_device.sh para provisionar o dispositivo.")
        return None

    ctx = None
    try:
        env = _tpm_env()
        # Carrega o objeto selado sob o SRK persistente
        with tempfile.NamedTemporaryFile(suffix=".ctx", delete=False) as tf:
            ctx = tf.name
        subprocess.run(
            ["tpm2_load", "-C", TPM_SRK_HANDLE, "-u", pub, "-r", priv, "-c", ctx],
            capture_output=True, check=True, env=env,
        )
        # Unseal — saída capturada em memória (stdout), nunca em disco
        result = subprocess.run(
            ["tpm2_unseal", "-c", ctx],
            capture_output=True, check=True, env=env,
        )
        secret = result.stdout.decode().strip()
        if secret:
            print(f"[TPM] Segredo TOTP de '{DEVICE_ID}' recuperado do TPM (somente RAM).")
            return secret
        print("[TPM] Unseal retornou vazio.")
        return None
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="replace")
        print(f"[TPM] Falha ao recuperar segredo do TPM: {stderr}")
        print("      Causas comuns: PCRs alterados, SRK ausente, blobs de outro dispositivo.")
        return None
    finally:
        if ctx and os.path.exists(ctx):
            os.remove(ctx)
        try:
            subprocess.run(["tpm2_flushcontext", "-t"],
                           capture_output=True, env=_tpm_env())
        except Exception:
            pass


def resolve_secret() -> str:
    """Ordem: TPM (se disponível) -> fallback OTP_SECRET (.env). Sai se nada."""
    if check_tpm():
        print("Hardware TPM detectado.")
        secret = unseal_otp_secret()
        if secret:
            return secret
        print("[TPM] Não foi possível recuperar o segredo do TPM.")
    else:
        print("AVISO: TPM não encontrado — tentando fallback .env (modo desenvolvimento).")

    if FALLBACK_OTP_SECRET:
        print("[dev] Usando OTP_SECRET do .env.")
        return FALLBACK_OTP_SECRET

    print("ERRO CRÍTICO: nenhum segredo TOTP disponível (TPM falhou e OTP_SECRET ausente).")
    sys.exit(1)


def do_login() -> str | None:
    """Abre a sessão no servidor e retorna o session_token."""
    payload = {"device_id": DEVICE_ID}
    if API_USER and API_PASS:
        payload["username"] = API_USER
        payload["password"] = API_PASS
    try:
        resp = requests.post(f"{API_URL}/login", json=payload,
                             timeout=10, verify=_VERIFY)
        resp.raise_for_status()
        token = resp.json().get("session_token")
        print(f"[*] Logado com sucesso (device '{DEVICE_ID}').")
        return token
    except requests.HTTPError:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            pass
        print(f"[!] Falha no login (HTTP {resp.status_code}): {detail}")
    except Exception as e:
        print(f"[!] Erro de conexão no login: {e}")
    return None


def main():
    # Resolve o segredo ANTES de contatar o servidor (falha cedo se indisponível)
    otp_secret = resolve_secret()
    totp = pyotp.TOTP(otp_secret, interval=OTP_INTERVAL)

    session_token = do_login()
    if not session_token:
        print("[!] Não foi possível abrir sessão. Encerrando.")
        sys.exit(1)

    print(f"Iniciando loop de autenticação OTP (modo de envio: {OTP_MODE})...")
    while True:
        otp_code = totp.now()
        if OTP_MODE == "plain":
            # Legado: envia o código em texto claro (só protegido por TLS).
            payload = {"session_token": session_token, "otp_code": otp_code}
            print("[>] Enviando OTP (plain).")
        else:
            # Default: envelope HMAC — o OTP nunca trafega em claro.
            envelope = seal_otp(otp_secret, otp_code)
            payload = {"session_token": session_token, "envelope": envelope}
            print(f"[>] Enviando envelope HMAC (nonce={envelope['nonce'][:8]}…).")
        try:
            check = requests.post(
                f"{API_URL}/verify",
                json=payload,
                timeout=10, verify=_VERIFY,
            )
            if check.status_code == 200:
                print("[+] Servidor confirmou: sessão ativa.")
            else:
                detail = ""
                try:
                    detail = check.json().get("detail", "")
                except Exception:
                    pass
                print(f"[-] Verificação recusada (HTTP {check.status_code}): {detail}")
                # Sessão pode ter sido derrubada — tenta relogar
                session_token = do_login()
                if not session_token:
                    print("[!] Não foi possível reabrir a sessão. Encerrando.")
                    break
        except Exception as e:
            print(f"[!] Erro de conexão na verificação: {e}")

        time.sleep(OTP_INTERVAL)


if __name__ == "__main__":
    main()
