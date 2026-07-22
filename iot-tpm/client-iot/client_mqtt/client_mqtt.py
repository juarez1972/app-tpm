"""
Cliente MQTT — dispositivo IoT (IoT-TPM)

Autentica-se periodicamente no servidor via TOTP. O segredo TOTP fica SELADO
no TPM do dispositivo e é recuperado apenas em memória (nunca gravado em disco
em texto claro). Em modo de desenvolvimento, aceita OTP_SECRET via .env.

Recuperação do segredo (mesma convenção do projeto vault-tpm):
  - SRK persistente:            TPM_SRK_HANDLE (default 0x81010001)
  - Blobs selados (por device): <TPM_DATA_DIR>/<device_id>_otp.enc.pub / .priv
  - Recuperação:                tpm2_load + tpm2_unseal (saída só para stdout/RAM)

O provisionamento (gerar o segredo, registrar no Vault do servidor e selar no
TPM do cliente) é feito por scripts/init_device.sh — veja o README (Seção 6).
"""

import os
import sys
import time
import json
import subprocess
import tempfile

import paho.mqtt.client as mqtt
import pyotp
from dotenv import load_dotenv

from crypto_envelope import seal_otp

load_dotenv()

# ── Configuração ──────────────────────────────────────────────────────────────
CLIENT_ID    = os.getenv("DEVICE_ID", "device-001")
MQTT_BROKER  = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "8883"))
MQTT_TOPIC   = os.getenv("MQTT_TOPIC_VERIFY", "iot/verify")
CA_CERT      = os.getenv("CA_CERT")        # opcional — TLS só ativo se o arquivo existir
OTP_INTERVAL = int(os.getenv("OTP_INTERVAL", "60"))
# Modo de envio: 'hmac' (envelope HMAC, default) ou 'plain' (legado).
OTP_MODE     = os.getenv("OTP_MODE", "hmac").strip().lower()

# TPM
TPM_DATA_DIR   = os.getenv("TPM_DATA_DIR", "./tpm-data")
TPM_SRK_HANDLE = os.getenv("TPM_SRK_HANDLE", "0x81010001")
TPM2TOOLS_TCTI = os.getenv("TPM2TOOLS_TCTI", "device:/dev/tpmrm0")

# Fallback de desenvolvimento (sem TPM)
FALLBACK_OTP_SECRET = os.getenv("OTP_SECRET")


def _tpm_env() -> dict:
    env = os.environ.copy()
    env["TPM2TOOLS_TCTI"] = TPM2TOOLS_TCTI
    return env


def check_tpm() -> bool:
    """Verifica se o TPM está presente e funcional."""
    try:
        subprocess.run(
            ["tpm2_getrandom", "4"],
            capture_output=True, check=True, env=_tpm_env(),
        )
        return True
    except Exception:
        return False


def unseal_otp_secret() -> str | None:
    """
    Recupera o segredo TOTP selado no TPM, retornando-o apenas em memória.
    Blobs esperados: <TPM_DATA_DIR>/<CLIENT_ID>_otp.enc.pub / .priv
    Nunca grava o segredo em texto claro no disco.
    """
    pub  = os.path.join(TPM_DATA_DIR, f"{CLIENT_ID}_otp.enc.pub")
    priv = os.path.join(TPM_DATA_DIR, f"{CLIENT_ID}_otp.enc.priv")

    if not (os.path.isfile(pub) and os.path.isfile(priv)):
        print(f"[TPM] Blobs selados não encontrados para '{CLIENT_ID}':")
        print(f"      esperado: {pub} / {priv}")
        print("      Rode scripts/init_device.sh para provisionar o dispositivo.")
        return None

    ctx = None
    try:
        env = _tpm_env()
        # Carrega o objeto selado sob o SRK persistente
        with tempfile.NamedTemporaryFile(suffix=".ctx", delete=False) as tf:
            ctx = tf.name
        subprocess.run(
            ["tpm2_load", "-C", TPM_SRK_HANDLE, "-u", pub, "-r", priv, "-c", ctx],
            capture_output=True, check=True, env=env,
        )
        # Unseal — saída capturada em memória (stdout), nunca em disco
        result = subprocess.run(
            ["tpm2_unseal", "-c", ctx],
            capture_output=True, check=True, env=env,
        )
        secret = result.stdout.decode().strip()
        if secret:
            print(f"[TPM] Segredo TOTP de '{CLIENT_ID}' recuperado do TPM (somente RAM).")
            return secret
        print("[TPM] Unseal retornou vazio.")
        return None
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="replace")
        print(f"[TPM] Falha ao recuperar segredo do TPM: {stderr}")
        print("      Causas comuns: PCRs alterados, SRK ausente, blobs de outro dispositivo.")
        return None
    finally:
        # Descarta o contexto do TPM e a sessão transitória
        if ctx and os.path.exists(ctx):
            os.remove(ctx)
        try:
            subprocess.run(["tpm2_flushcontext", "-t"],
                           capture_output=True, env=_tpm_env())
        except Exception:
            pass


def resolve_secret() -> str:
    """Ordem: TPM (se disponível) -> fallback OTP_SECRET (.env). Sai se nada."""
    if check_tpm():
        print("Hardware TPM detectado.")
        secret = unseal_otp_secret()
        if secret:
            return secret
        print("[TPM] Não foi possível recuperar o segredo do TPM.")
    else:
        print("AVISO: TPM não encontrado — tentando fallback .env (modo desenvolvimento).")

    if FALLBACK_OTP_SECRET:
        print("[dev] Usando OTP_SECRET do .env.")
        return FALLBACK_OTP_SECRET

    print("ERRO CRÍTICO: nenhum segredo TOTP disponível (TPM falhou e OTP_SECRET ausente).")
    sys.exit(1)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Conectado ao broker MQTT.")
        client.subscribe(f"iot/response/{CLIENT_ID}")
    else:
        print(f"Falha na conexão ao broker MQTT (rc={rc}).")


def on_message(client, userdata, msg):
    print(f"RESPOSTA DO SERVIDOR: {msg.payload.decode()}")


def main():
    # Resolve o segredo ANTES de abrir a conexão (falha cedo se indisponível)
    otp_secret = resolve_secret()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message

    # TLS: ativo somente se CA_CERT estiver definido e o arquivo existir
    if CA_CERT and os.path.isfile(CA_CERT):
        client.tls_set(ca_certs=CA_CERT)
        print(f"TLS ativo (CA: {CA_CERT}).")
    else:
        print("AVISO: Certificado CA não encontrado — conexão sem TLS (modo desenvolvimento).")
        print(f"       CA_CERT={CA_CERT!r}  |  Caminho esperado: ./certs/ca.crt")

    try:
        print(f"Tentando conectar ao broker MQTT em {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()
    except ConnectionRefusedError:
        print("Broker MQTT offline ou inacessível. Mantendo o contêiner vivo para testes locais.")
    except Exception as e:
        print(f"Erro ao conectar: {e}")

    totp = pyotp.TOTP(otp_secret, interval=OTP_INTERVAL)
    print(f"Iniciando loop de autenticação OTP (modo de envio: {OTP_MODE})...")
    while True:
        otp_code = totp.now()
        if OTP_MODE == "plain":
            payload = {"client_id": CLIENT_ID, "otp_code": otp_code}
            print("Enviando OTP (plain).")
        else:
            # Envelope HMAC — o OTP nunca trafega em claro.
            envelope = seal_otp(otp_secret, otp_code)
            payload = {"client_id": CLIENT_ID, "envelope": envelope}
            print(f"Enviando envelope HMAC (nonce={envelope['nonce'][:8]}…).")
        try:
            client.publish(MQTT_TOPIC, json.dumps(payload))
        except Exception as e:
            print(f"Erro ao publicar mensagem: {e}")
        time.sleep(OTP_INTERVAL)


if __name__ == "__main__":
    main()
