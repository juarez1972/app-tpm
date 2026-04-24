from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import pyotp
import uvicorn
import secrets

app = FastAPI()

# Configurações de Teste (Em produção, use variáveis de ambiente)
FIXED_USER = "cliente-otp"
FIXED_PASS = "senha-aleatoria-123"
# Geramos uma secret para o TOTP (Base32)
OTP_SECRET = pyotp.random_base32()
# Simulamos uma base de tokens ativos
active_sessions = set()

class LoginRequest(BaseModel):
    username: str
    password: str

class OTPRequest(BaseModel):
    token: str
    otp_code: str

@app.get("/setup")
def setup():
    """Endpoint para você saber qual segredo configurar no cliente"""
    return {"user": FIXED_USER, "otp_secret": OTP_SECRET, "interval": "60s"}

@app.post("/login")
def login(req: LoginRequest):
    if req.username == FIXED_USER and req.password == FIXED_PASS:
        # Gera um token de sessão aleatório
        session_token = secrets.token_hex(16)
        active_sessions.add(session_token)
        return {"session_token": session_token, "message": "Login realizado. Envie o OTP."}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

@app.post("/verify")
def verify(req: OTPRequest):
    if req.token not in active_sessions:
        raise HTTPException(status_code=403, detail="Sessão inexistente ou encerrada.")

    totp = pyotp.TOTP(OTP_SECRET, interval=60)
    
    if totp.verify(req.otp_code):
        return {"status": "valid", "message": "Conexão mantida."}
    else:
        # "Derruba" a sessão se o OTP falhar
        active_sessions.remove(req.token)
        raise HTTPException(status_code=401, detail="OTP inválido. Sessão encerrada.")

if __name__ == "__main__":
    print(f"DEBUG: Secret para o cliente: {OTP_SECRET}")
    uvicorn.run(app, host="0.0.0.0", port=5000)
