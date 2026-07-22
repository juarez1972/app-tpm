"""
Servidor MQTT (subscriber) — IoT-TPM

Valida a autenticação TOTP dos dispositivos IoT. O segredo TOTP de cada
dispositivo é lido do HashiCorp Vault (KV v2), indexado pelo device_id, com
fallback para uma variável de ambiente OTP_SECRET em modo de desenvolvimento.

Fluxo por mensagem:
  1. Cliente publica em MQTT_TOPIC_VERIFY: {"client_id": "<id>", "otp_code": "123456"}
  2. Servidor busca o segredo do dispositivo (Vault -> fallback .env) e cacheia.
  3. Valida o código TOTP (intervalo de 60 s) e responde em iot/response/<id>.

Integração com o projeto vault-tpm:
  - Mount KV v2 padrão: 'secret'
  - Path por dispositivo: secret/data/tpm-verified/iot/devices/<device_id>
    (coberto pela policy 'app-policy' -> secret/data/tpm-verified/*)
  - Campo do segredo dentro do secret: 'otp_secret'
  - Autenticação no Vault via VAULT_TOKEN (ex.: o app_token recuperado do TPM
    no lado servidor pelo scripts/get_root_token.sh do vault-tpm).
"""

import os
import sys
import json

import paho.mqtt.client as mqtt
import pyotp
from dotenv import load_dotenv

try:
    import hvac
except ImportError:  # hvac é opcional em modo puramente .env
    hvac = None

load_dotenv()

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "8883"))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC_VERIFY", "iot/verify")
OTP_INTERVAL = int(os.getenv("OTP_INTERVAL", "60"))

# TLS (opcional — ativo somente se os arquivos existirem)
CA_CERT     = os.getenv("CA_CERT")
SERVER_CERT = os.getenv("SERVER_CERT")
SERVER_KEY  = os.getenv("SERVER_KEY")

# Vault
VAULT_ADDR   = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN  = os.getenv("VAULT_TOKEN")
VAULT_KV_MOUNT   = os.getenv("VAULT_KV_MOUNT", "secret")
VAULT_DEVICE_BASE = os.getenv("VAULT_DEVICE_BASE", "tpm-verified/iot/devices")
VAULT_SECRET_FIELD = os.getenv("VAULT_SECRET_FIELD", "otp_secret")

# Fallback de desenvolvimento: um único segredo em .env (sem Vault)
FALLBACK_OTP_SECRET = os.getenv("OTP_SECRET")

# Cache em memória: device_id -> otp_secret
_secret_cache: dict[str, str] = {}


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
            print(f"[Vault] Autenticado em {VAULT_ADDR}.")
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
        otp_code  = str(data.get("otp_code", ""))
        client_id = data.get("client_id")

        if not client_id or not otp_code:
            print("[-] Mensagem inválida (client_id/otp_code ausente).")
            return

        response_topic = f"iot/response/{client_id}"
        secret = load_device_secret(client_id)

        if secret is None:
            client.publish(response_topic, json.dumps(
                {"status": "error", "msg": "Dispositivo não provisionado no servidor"}))
            return

        totp = pyotp.TOTP(secret, interval=OTP_INTERVAL)
        if totp.verify(otp_code, valid_window=1):
            print(f"[+] OTP válido do cliente {client_id}")
            client.publish(response_topic, json.dumps(
                {"status": "valid", "msg": "Acesso concedido"}))
        else:
            print(f"[-] OTP inválido do cliente {client_id}")
            client.publish(response_topic, json.dumps(
                {"status": "invalid", "msg": "Acesso negado"}))

    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")


def main():
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

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"ERRO: Não foi possível conectar ao broker {MQTT_BROKER}:{MQTT_PORT} — {e}")
        sys.exit(1)

    print("Servidor MQTT iniciado. Aguardando mensagens...")
    client.loop_forever()


if __name__ == "__main__":
    main()
