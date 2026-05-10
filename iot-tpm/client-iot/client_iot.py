import requests
import pyotp
import time
import subprocess
from pathlib import Path

# Configurações obtidas do servidor ou enviadas previamente
URL = "http://127.0.0.1:5000"
USER = "cliente-otp"
PASS = "senha-aleatoria-123"
# Esta secret deve ser a mesma do servidor obtida no endpoint /setup
OTP_SECRET = "M3WC34V7LQWG6HR6K6HAVO23GPNRFFKA" 

def check_tpm_status():
    """Verifica se o TPM está operacional"""
    try:
        # Tenta gerar um número aleatório via TPM para validar funcionamento
        result = subprocess.run(['tpm2_getrandom', '4', '--tcti', 'device:/dev/tpmrm0'], 
                                capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False [cite: 9, 31]

def start_client():
    if not check_tpm_status():
        print("[!] Erro: TPM não detectado ou inativo. Abortando.")
        return

    # 1. Login Inicial
    try:
        response = requests.post(f"{URL}/login", json={"username": USER, "password": PASS})
        response.raise_for_status()
        session_token = response.json().get("session_token")
        print(f"[*] Logado com sucesso. Token: {session_token}") [cite: 4, 26]

        totp = pyotp.TOTP(OTP_SECRET, interval=60)

        # 2. Loop de verificação a cada minuto
        while True:
            otp_atual = totp.now()
            print(f"[>] Enviando OTP: {otp_atual}...")
            
            check = requests.post(f"{URL}/verify", json={
                "token": session_token,
                "otp_code": otp_atual
            })
            
            if check.status_code == 200:
                print("[+] Servidor confirmou: Sessão Ativa.")
            else:
                print(f"[-] Erro: {check.json()['detail']}")
                break
            
            time.sleep(60) # Aguarda o próximo ciclo [cite: 5, 27]
            
    except Exception as e:
        print(f"[!] Erro de conexão: {e}")

if __name__ == "__main__":
    start_client()
