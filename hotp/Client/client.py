import requests
import pyotp
import time

# Configurações obtidas do servidor ou enviadas previamente
URL = "http://127.0.0.1:5000"
USER = "cliente-otp"
PASS = "senha-aleatoria-123"
# Esta secret deve ser a mesma do servidor
OTP_SECRET = "M3WC34V7LQWG6HR6K6HAVO23GPNRFFKA" 

def start_client():
    # 1. Login Inicial
    try:
        response = requests.post(f"{URL}/login", json={"username": USER, "password": PASS})
        response.raise_for_status()
        session_token = response.json().get("session_token")
        print(f"[*] Logado com sucesso. Token: {session_token}")
        
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
                print("[!] A sessão foi derrubada pelo servidor.")
                break
            
            # Aguarda o próximo ciclo (60 segundos)
            time.sleep(60)

    except Exception as e:
        print(f"[!] Erro de conexão: {e}")

if __name__ == "__main__":
    # Primeiro rode o servidor, pegue a secret e coloque na variável OTP_SECRET
    start_client()
