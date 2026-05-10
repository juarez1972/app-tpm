import os
import hvac
import pyotp
import uvicorn
import secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Carregamento de variáveis de ambiente
VAULT_ADDR = os.getenv("VAULT_ADDR")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")
OTP_SECRET = os.getenv("OTP_SECRET")

def get_vault_client():
    try:
        client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
        if client.is_authenticated():
            return client
    except Exception as e:
        print(f"[!] Erro ao conectar no Vault: {e}")
    return None

@app.get("/status-vault")
def vault_status():
    client = get_vault_client()
    if client:
        return {"status": "conectado", "addr": VAULT_ADDR}
    return {"status": "desconectado"}

@app.post("/verify")
def verify(req: OTPRequest):
    # Logica de verificação mantida conforme config_hotp.pdf
    totp = pyotp.TOTP(OTP_SECRET, interval=60)
    if totp.verify(req.otp_code):
        return {"status": "valid"}
    raise HTTPException(status_code=401, detail="OTP inválido")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
