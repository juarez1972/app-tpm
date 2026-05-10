import os
import time
import json
import paho.mqtt.client as mqtt
import pyotp
import subprocess
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = "device-001"
OTP_SECRET = os.getenv("OTP_SECRET")

def check_tpm():
    try:
        subprocess.run(['tpm2_getrandom', '4'], capture_output=True, check=True)
        return True
    except:
        return False

def on_connect(client, userdata, flags, rc):
    client.subscribe(f"iot/response/{CLIENT_ID}")

def on_message(client, userdata, msg):
    print(f"RESPOSTA DO SERVIDOR: {msg.payload.decode()}")

if not check_tpm():
    print("ERRO: TPM não encontrado!")
    exit(1)

client = mqtt.Client(client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message

client.tls_set(ca_certs=os.getenv("CA_CERT"))

client.connect(os.getenv("MQTT_BROKER"), int(os.getenv("MQTT_PORT")))
client.loop_start()

totp = pyotp.TOTP(OTP_SECRET, interval=60)

try:
    while True:
        payload = {
            "client_id": CLIENT_ID,
            "otp_code": totp.now()
        }
        print(f"Enviando OTP via TLS: {payload['otp_code']}")
        client.publish(os.getenv("MQTT_TOPIC_VERIFY"), json.dumps(payload))
        time.sleep(60)
except KeyboardInterrupt:
    client.disconnect()
