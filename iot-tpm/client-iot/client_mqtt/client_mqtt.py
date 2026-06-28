import os
import time
import json
import subprocess

import paho.mqtt.client as mqtt
import pyotp
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = "device-001"
OTP_SECRET = os.getenv("OTP_SECRET")


def check_tpm() -> bool:
    """Verifica se o hardware TPM está presente e funcional."""
    try:
        subprocess.run(
            ["tpm2_getrandom", "4"],
            capture_output=True,
            check=True,
        )
        return True
    except Exception:
        return False


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado ao broker MQTT.")
        client.subscribe(f"iot/response/{CLIENT_ID}")
    else:
        print(f"Falha na conexão ao broker MQTT (rc={rc}).")


def on_message(client, userdata, msg):
    print(f"RESPOSTA DO SERVIDOR: {msg.payload.decode()}")


# ── Verificação de integridade do hardware ────────────────────────────────────
if not check_tpm():
    print("ERRO CRÍTICO: TPM não encontrado ou não funcional. Abortando.")
    exit(1)

print("Hardware TPM detectado.")

# ── Configuração do cliente MQTT ──────────────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message
client.tls_set(ca_certs=os.getenv("CA_CERT"))

try:
    print("Tentando conectar ao broker MQTT...")
    client.connect(os.getenv("MQTT_BROKER"), int(os.getenv("MQTT_PORT")))
    client.loop_start()
except ConnectionRefusedError:
    print("Broker MQTT offline ou inacessível. Mantendo o contêiner vivo para testes locais.")
except Exception as e:
    print(f"Erro ao conectar: {e}")

# ── Loop de autenticação contínua via OTP ────────────────────────────────────
totp = pyotp.TOTP(OTP_SECRET, interval=60)

print("Aguardando testes de BCC e TPM via terminal...")
while True:
    payload = {
        "client_id": CLIENT_ID,
        "otp_code": totp.now(),
    }
    print(f"Enviando OTP via TLS: {payload['otp_code']}")
    try:
        client.publish(os.getenv("MQTT_TOPIC_VERIFY"), json.dumps(payload))
    except Exception as e:
        print(f"Erro ao publicar mensagem: {e}")
    time.sleep(60)
