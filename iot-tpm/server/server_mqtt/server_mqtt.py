import os
import sys
import json
import paho.mqtt.client as mqtt
import pyotp
import hvac
from dotenv import load_dotenv

load_dotenv()

# ── Variáveis de ambiente obrigatórias ───────────────────────────────────────
REQUIRED_ENV = ["OTP_SECRET", "MQTT_TOPIC_VERIFY"]
missing = [var for var in REQUIRED_ENV if not os.getenv(var)]
if missing:
    print(f"ERRO: Variáveis de ambiente ausentes ou vazias: {', '.join(missing)}")
    print("Crie o arquivo .env na raiz do projeto com base no README (Seção 5).")
    sys.exit(1)

MQTT_BROKER  = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_PORT", 8883))
OTP_SECRET   = os.getenv("OTP_SECRET")
MQTT_TOPIC   = os.getenv("MQTT_TOPIC_VERIFY")
CA_CERT      = os.getenv("CA_CERT")       # opcional — TLS só ativo se o arquivo existir
SERVER_CERT  = os.getenv("SERVER_CERT")
SERVER_KEY   = os.getenv("SERVER_KEY")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Conectado ao broker MQTT em {MQTT_BROKER}:{MQTT_PORT}.")
        client.subscribe(MQTT_TOPIC)
        print(f"Inscrito no tópico: {MQTT_TOPIC}")
    else:
        print(f"Falha na conexão ao broker MQTT (rc={rc}).")


def on_message(client, userdata, msg):
    try:
        data      = json.loads(msg.payload)
        otp_code  = data.get("otp_code")
        client_id = data.get("client_id")

        totp           = pyotp.TOTP(OTP_SECRET, interval=60)
        response_topic = f"iot/response/{client_id}"

        if totp.verify(otp_code):
            print(f"[+] OTP válido do cliente {client_id}")
            client.publish(response_topic, json.dumps({"status": "valid",   "msg": "Acesso concedido"}))
        else:
            print(f"[-] OTP inválido do cliente {client_id}")
            client.publish(response_topic, json.dumps({"status": "invalid", "msg": "Acesso negado"}))

    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")


# ── Configuração do cliente MQTT ──────────────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

# TLS: ativo somente se CA_CERT estiver definido e o arquivo existir
if CA_CERT and os.path.isfile(CA_CERT):
    certfile = SERVER_CERT if SERVER_CERT and os.path.isfile(SERVER_CERT) else None
    keyfile  = SERVER_KEY  if SERVER_KEY  and os.path.isfile(SERVER_KEY)  else None
    client.tls_set(ca_certs=CA_CERT, certfile=certfile, keyfile=keyfile)
    print(f"TLS ativo (CA: {CA_CERT}).")
else:
    print("AVISO: Certificado CA não encontrado — conexão sem TLS (modo desenvolvimento).")
    print(f"       CA_CERT={CA_CERT!r}  |  Caminho esperado: ./certs/ca.crt")

# ── Conexão e loop ────────────────────────────────────────────────────────────
try:
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
except Exception as e:
    print(f"ERRO: Não foi possível conectar ao broker {MQTT_BROKER}:{MQTT_PORT} — {e}")
    sys.exit(1)

print("Servidor MQTT iniciado. Aguardando mensagens...")
client.loop_forever()

