"""
Servidor REST API (FastAPI) — IoT-TPM

Valida a autenticação TOTP dos dispositivos IoT via HTTP. O segredo TOTP de cada
dispositivo é lido do HashiCorp Vault (KV v2), indexado pelo device_id, com
fallback para uma variável de ambiente OTP_SECRET em modo de desenvolvimento.

Fluxo:
  1. POST /login   {"device_id": "<id>"}                -> {"session_token": ...}
     (opcionalmente com credenciais estáticas API_USER/API_PASS, se definidas)
  2. POST /verify  {"session_token": ..., "otp_code": "123456"}
     -> o servidor busca o segredo do dispositivo (Vault -> fallback .env),
        cacheia e valida o código TOTP (intervalo padrão 60 s).

Integração com o projeto vault-tpm (mesma convenção do par MQTT):
  - Mount KV v2 padrão: 'secret'
  - Path por dispositivo: secret/data/tpm-verified/iot/devices/<device_id>
    (coberto pela policy 'app-policy' -> secret/data/tpm-verified/*)
  - Campo do segredo dentro do secret: 'otp_secret'
  - Autenticação no Vault via VAULT_TOKEN (ex.: o app_token recuperado do TPM
    no lado servidor pelo scripts/get_root_token.sh do vault-tpm).

IMPORTANTE: OTP_INTERVAL deve ser idêntico ao do cliente, senão todo código é
rejeitado.
"""

import os
import secrets

import pyotp
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    import hvac
except ImportError:  # hvac é opcional em modo puramente .env
    hvac = None

load_dotenv()

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "5000"))
OTP_INTERVAL = int(os.getenv("OTP_INTERVAL", "60"))

# Credenciais estáticas OPCIONAIS para o /login (além do device_id).
# Se ambas estiverem vazias, o login exige apenas um device_id válido.
API_USER = os.getenv("API_USER")
API_PASS = os.getenv("API_PASS")

# Vault
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")
VAULT_KV_MOUNT = os.getenv("VAULT_KV_MOUNT", "secret")
VAULT_DEVICE_BASE = os.getenv("VAULT_DEVICE_BASE", "tpm-verified/iot/devices")
VAULT_SECRET_FIELD = os.getenv("VAULT_SECRET_FIELD", "otp_secret")

# Fallback de desenvolvimento: um único segredo em .env (sem Vault)
FALLBACK_OTP_SECRET = os.getenv("OTP_SECRET")

# Cache em memória: device_id -> otp_secret
_secret_cache: dict[str, str] = {}
# Sessões ativas: session_token -> device_id
active_sessions: dict[str, str] = {}

app = FastAPI(title="IoT-TPM REST Auth", version="1.0.0")


# ── Modelos ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    device_id: str
    username: str | None = None
    password: str | None = None


class OTPRequest(BaseModel):
    session_token: str
    otp_code: str


# ── Vault ─────────────────────────────────────────────────────────────────────
def get_vault_client():
    """Cria e autentica um cliente Vault. Retorna None se indisponível."""
    if hvac is None:
        print("[Vault] Biblioteca 'hvac' não instalada — usando fallback .env.")
        return None
    if not VAULT_TOKEN:
        print("[Vault] VAULT_TOKEN não definido — usando fallback .env.")
        return None
    try:
        client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
        if client.is_authenticated():
            return client
        print(f"[Vault] Falha de autenticação em {VAULT_ADDR} — usando fallback .env.")
    except Exception as e:
        print(f"[Vault] Erro ao conectar ({e}) — usando fallback .env.")
    return None


def load_device_secret(device_id: str) -> str | None:
    """
    Recupera o segredo TOTP do dispositivo.
    Ordem: cache -> Vault (KV v2) -> fallback OTP_SECRET (.env).
    """
    if not device_id:
        return None

    if device_id in _secret_cache:
        return _secret_cache[device_id]

    # 1) Vault
    client = get_vault_client()
    if client is not None:
        path = f"{VAULT_DEVICE_BASE}/{device_id}"
        try:
            resp = client.secrets.kv.v2.read_secret_version(
                mount_point=VAULT_KV_MOUNT,
                path=path,
                raise_on_deleted_version=True,
            )
            data = resp["data"]["data"]
            secret = data.get(VAULT_SECRET_FIELD)
            if secret:
                print(f"[Vault] Segredo do dispositivo '{device_id}' carregado de "
                      f"{VAULT_KV_MOUNT}/data/{path}.")
                _secret_cache[device_id] = secret
                return secret
            print(f"[Vault] Campo '{VAULT_SECRET_FIELD}' ausente para '{device_id}'.")
        except Exception as e:
            print(f"[Vault] Segredo de '{device_id}' não encontrado no Vault ({e}).")

    # 2) Fallback .env (modo dev)
    if FALLBACK_OTP_SECRET:
        print(f"[dev] Usando OTP_SECRET do .env para o dispositivo '{device_id}'.")
        _secret_cache[device_id] = FALLBACK_OTP_SECRET
        return FALLBACK_OTP_SECRET

    print(f"[ERRO] Nenhum segredo disponível para o dispositivo '{device_id}' "
          f"(Vault indisponível e OTP_SECRET não definido).")
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status-vault")
def vault_status():
    client = get_vault_client()
    if client:
        return {"status": "conectado", "addr": VAULT_ADDR}
    return {"status": "desconectado", "addr": VAULT_ADDR}


@app.post("/login")
def login(req: LoginRequest):
    """
    Abre uma sessão para o dispositivo. Valida credenciais estáticas apenas se
    API_USER/API_PASS estiverem configuradas. O dispositivo precisa estar
    provisionado (segredo presente no Vault ou fallback .env).
    """
    if API_USER and API_PASS:
        if req.username != API_USER or req.password != API_PASS:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    if load_device_secret(req.device_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dispositivo '{req.device_id}' não provisionado no servidor.",
        )

    session_token = secrets.token_hex(16)
    active_sessions[session_token] = req.device_id
    return {"session_token": session_token, "message": "Login realizado. Envie o OTP."}


@app.post("/verify")
def verify(req: OTPRequest):
    device_id = active_sessions.get(req.session_token)
    if device_id is None:
        raise HTTPException(status_code=403, detail="Sessão inexistente ou encerrada.")

    secret = load_device_secret(device_id)
    if secret is None:
        raise HTTPException(status_code=404, detail="Segredo do dispositivo indisponível.")

    totp = pyotp.TOTP(secret, interval=OTP_INTERVAL)
    if totp.verify(req.otp_code, valid_window=1):
        print(f"[+] OTP válido do dispositivo {device_id}")
        return {"status": "valid", "message": "Conexão mantida."}

    # OTP inválido: derruba a sessão
    active_sessions.pop(req.session_token, None)
    print(f"[-] OTP inválido do dispositivo {device_id} — sessão encerrada.")
    raise HTTPException(status_code=401, detail="OTP inválido. Sessão encerrada.")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
