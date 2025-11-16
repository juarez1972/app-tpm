import subprocess
import os
import sys
import time

# Caminhos definidos no Dockerfile
SEALED_PUB = "/app/sealed_key.pub"
SEALED_PRIV = "/app/sealed_key.priv"
# Local seguro na memória RAM (tmpfs)
PLAINTEXT_KEY_PATH = "/run/secrets/service_key.json" 
TPM_DEVICE = "/dev/tpmrm0"

def log(message):
    print(f" {message}", flush=True)

def check_tpm():
    if not os.path.exists(TPM_DEVICE):
        log(f"ERRO CRÍTICO: Dispositivo {TPM_DEVICE} não encontrado.")
        log("Verifique se 'dtoverlay=tpm-slb9670' (RPi) ou overlay SPI (OrangePi) está ativo.")
        sys.exit(1)
    log("Hardware TPM detectado.")

def unseal_key():
    log("1. Criando Contexto Primário (SRK)...")
    try:
        # Cria a chave primária na hierarquia de endosso
        subprocess.check_call([
            "tpm2_createprimary",
            "-C", "e",             # Endorsement Hierarchy
            "-g", "sha256",
            "-G", "rsa",
            "-c", "primary.ctx"
        ])
    except subprocess.CalledProcessError as e:
        log(f"Falha ao criar contexto primário: {e}")
        sys.exit(1)

    log("2. Carregando Objeto Selado na Memória do TPM...")
    try:
        # CORREÇÃO: Argumentos adicionados para carregar as partes pública e privada
        subprocess.check_call()
    except subprocess.CalledProcessError as e:
        log(f"Falha ao carregar objeto (verifique se os arquivos.pub/.priv existem): {e}")
        sys.exit(1)

    log("3. Descriptografando Chave de Serviço (Unseal)...")
    try:
        # Escreve a saída diretamente no tmpfs (RAM)
        with open(PLAINTEXT_KEY_PATH, "wb") as f:
            subprocess.check_call([
                "tpm2_unseal",
                "-c", "key.ctx"
            ], stdout=f)
        
        # Verifica se o arquivo não está vazio
        if os.path.getsize(PLAINTEXT_KEY_PATH) > 0:
            log(f"Sucesso! Chave recuperada em {PLAINTEXT_KEY_PATH}")
        else:
            raise Exception("O arquivo recuperado está vazio.")
            
    except Exception as e:
        log(f"FALHA DE SEGURANÇA OU INTEGRIDADE: O TPM recusou descriptografar. {e}")
        log("Causas possíveis: PCRs alterados (boot inseguro), Hardware diferente, ou erro de I/O.")
        sys.exit(1)
    
    # Limpeza segura de artefatos do TPM
    if os.path.exists("primary.ctx"): os.remove("primary.ctx")
    if os.path.exists("key.ctx"): os.remove("key.ctx")

def start_twingate():
    log("Configurando Twingate...")
    
    # CORREÇÃO: Comando setup completo
    setup_cmd =
    
    try:
        subprocess.check_call(setup_cmd)
        log("Setup do Twingate concluído com sucesso.")
    except subprocess.CalledProcessError as e:
        log(f"Setup falhou: {e}")
        sys.exit(1)

    # Destruição imediata da chave em texto plano da RAM
    if os.path.exists(PLAINTEXT_KEY_PATH):
        os.remove(PLAINTEXT_KEY_PATH)
        log("Chave em texto plano removida da memória.")

    log("Iniciando serviço...")
    # O comando 'twingate start' roda o daemon em background, mas precisamos manter o container vivo.
    # A melhor abordagem em Docker é rodar o daemon em foreground se possível, 
    # mas o cliente Linux Twingate é um serviço systemd/daemon.
    try:
        subprocess.check_call(["twingate", "start"])
    except subprocess.CalledProcessError as e:
        log(f"Erro ao iniciar serviço: {e}")
        sys.exit(1)

    # Loop infinito para manter o container rodando e monitorar o status
    log("Serviço ativo. Monitorando...")
    while True:
        time.sleep(60)
        # Opcional: Check de saúde simples
        result = subprocess.run(["twingate", "status"], capture_output=True, text=True)
        if "online" not in result.stdout and "online" not in result.stderr:
             log("Aviso: Twingate pode estar desconectado.")

if __name__ == "__main__":
    check_tpm()
    unseal_key()
    start_twingate()
