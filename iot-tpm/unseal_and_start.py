import subprocess
import os
import sys
import time

# Configuração
SEALED_PUB = "/app/sealed_key.pub"
SEALED_PRIV = "/app/sealed_key.priv"
# Este caminho DEVE estar em um volume tmpfs para segurança
PLAINTEXT_KEY_PATH = "/run/secrets/service_key.json" 
TPM_DEVICE = "/dev/tpmrm0"

def log(message):
    print(f" {message}", flush=True)

def check_tpm():
    if not os.path.exists(TPM_DEVICE):
        log(f"Erro Crítico: Dispositivo TPM {TPM_DEVICE} não encontrado.")
        # Em falha de hardware, encerramos para evitar boot inseguro
        sys.exit(1)
    log("Dispositivo TPM detectado.")

def unseal_key():
    log("Inicializando contexto TPM...")
    
    # 1. Criar Contexto Primário (SRK)
    # Utilizamos o template padrão (RSA 2048, AES 128 CFB) na hierarquia de endosso
    try:
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

    # 2. Carregar o Objeto Selado
    # Carrega o blob criptografado na memória do TPM, envelopado pelo contexto primário
    try:
        subprocess.check_call()
    except subprocess.CalledProcessError as e:
        log(f"Falha ao carregar objeto selado: {e}")
        sys.exit(1)

    # 3. Unseal dos Dados (Descriptografia)
    # A saída é escrita DIRETAMENTE no caminho tmpfs seguro
    log("Realizando unseal da chave de serviço...")
    try:
        with open(PLAINTEXT_KEY_PATH, "wb") as f:
            subprocess.check_call([
                "tpm2_unseal",
                "-c", "key.ctx"
            ], stdout=f)
        log(f"Chave recuperada com sucesso em {PLAINTEXT_KEY_PATH}")
    except subprocess.CalledProcessError as e:
        log(f"Falha ao realizar unseal (verifique PCRs/Estado do Sistema): {e}")
        sys.exit(1)
    
    # Limpeza de contextos temporários do disco (os handles do TPM são limpos pelo RM)
    if os.path.exists("primary.ctx"): os.remove("primary.ctx")
    if os.path.exists("key.ctx"): os.remove("key.ctx")

def start_twingate():
    log("Configurando Cliente Twingate Headless...")
    
    # Executar setup usando a chave recuperada
    # O comando setup --headless aceita o caminho do arquivo de chave 
    try:
        setup_cmd =
        subprocess.check_call(setup_cmd)
        log("Setup do Twingate concluído.")
    except subprocess.CalledProcessError as e:
        log(f"Setup do Twingate falhou: {e}")
        sys.exit(1)

    # Apagar a chave da memória/tmpfs IMEDIATAMENTE após o setup
    # O Twingate importa a chave para seu armazenamento interno (/var/lib/twingate)
    # Portanto, o arquivo JSON original não é mais necessário e deve ser destruído.
    if os.path.exists(PLAINTEXT_KEY_PATH):
        os.remove(PLAINTEXT_KEY_PATH)
        log("Chave em texto plano removida do tmpfs.")

    # Iniciar o serviço Twingate
    log("Iniciando Serviço Twingate...")
    try:
        subprocess.check_call(["twingate", "start"])
    except subprocess.CalledProcessError as e:
        log(f"Falha ao iniciar Twingate: {e}")
        sys.exit(1)

    # Loop de monitoramento
    # Mantém o contêiner ativo e monitora o status do serviço
    log("Entrando em loop de monitoramento.")
    while True:
        time.sleep(60)
        # Opcional: Adicionar lógica para verificar 'twingate status' e reiniciar se necessário

if __name__ == "__main__":
    check_tpm()
    unseal_key()
    start_twingate()
