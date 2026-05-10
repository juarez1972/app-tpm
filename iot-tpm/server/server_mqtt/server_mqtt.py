import os
import paho.mqtt.client as mqtt
import pyotp
import json
import hvac
from dotenv import load_dotenv

load_dotenv()

# Configs
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
OTP_SECRET = os.getenv("OTP_SECRET")

def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao Broker com resultado: {rc}")
    client.subscribe(os.getenv("MQTT_TOPIC_VERIFY"))

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        otp_code = data.get("otp_code")
        client_id = data.get("client_id")
        
        totp = pyotp.TOTP(OTP_SECRET, interval=60)
        
        response_topic = f"iot/response/{client_id}"
        
        if totp.verify(otp_code):
            print(f"[+] OTP Válido do cliente {client_id}")
            client.publish(response_topic, json.dumps({"status": "valid", "msg": "Acesso concedido"}))
        else:
            print(f"[-] OTP Inválido do cliente {client_id}")
            client.publish(response_topic, json.dumps({"status": "invalid", "msg": "Acesso negado"}))
            
    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Configuração TLS
client.tls_set(ca_certs=os.getenv("CA_CERT"),
               certfile=os.getenv("SERVER_CERT"),
               keyfile=os.getenv("SERVER_KEY"))

client.connect(MQTT_BROKER, MQTT_PORT, 60)
print("Servidor MQTT iniciado (Aguardando mensagens via TLS)...")
client.loop_forever()
