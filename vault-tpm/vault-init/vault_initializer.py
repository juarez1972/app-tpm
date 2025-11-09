#!/usr/bin/env python3
import requests
import time
import os
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VaultInitializer:
    def __init__(self):
        self.tpm_validator_url = os.getenv('TPM_VALIDATOR_URL', 'http://tpm-validator:5000')
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8200')
        self.max_retries = 30
        self.retry_delay = 5
        self.tpm_data_dir = Path('/app/tpm-data')

    def check_tpm_data_exists(self):
        """Verifica se os dados do TPM existem"""
        required_files = ['secret', 'vault-root-key']
        for file in required_files:
            if not (self.tpm_data_dir / file).exists():
                logger.error(f"Arquivo necessário não encontrado: {file}")
                return False
        return True

    def wait_for_tpm_validation(self):
        """Aguarda a validação do TPM"""
        logger.info("Aguardando validação do TPM...")
        
        if not self.check_tpm_data_exists():
            logger.error("Dados do TPM não encontrados. Execute setup_secret.sh primeiro.")
            return False
        
        for i in range(self.max_retries):
            try:
                response = requests.get(f"{self.tpm_validator_url}/status", timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    if status.get('tpm_validated'):
                        logger.info("TPM validado com sucesso!")
                        return True
                    else:
                        logger.info(f"TPM ainda não validado... Tentativa {i+1}/{self.max_retries}")
                else:
                    logger.warning(f"Resposta inesperada do validador TPM: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro ao conectar com validador TPM: {e}")
            
            if i < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error("Timeout aguardando validação do TPM")
        return False

    def is_vault_initialized(self):
        """Verifica se o Vault já está inicializado"""
        try:
            response = requests.get(f"{self.vault_addr}/v1/sys/health", timeout=10)
            # Código 200 = inicializado e unsealed
            # Código 429 = inicializado mas sealed (standby)
            # Código 501 = não inicializado
            # Código 503 = sealed
            if response.status_code in [200, 429, 503]:
                return True
            elif response.status_code == 501:
                return False
            else:
                logger.warning(f"Status code inesperado do Vault: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao verificar inicialização do Vault: {e}")
            return False

    def initialize_vault(self):
        """Inicializa o Vault se necessário"""
        try:
            if not self.is_vault_initialized():
                logger.info("Inicializando Vault...")
                
                with open(self.tpm_data_dir / 'vault-root-key', 'r') as f:
                    root_key = f.read().strip()
                
                init_response = requests.put(
                    f"{self.vault_addr}/v1/sys/init",
                    json={
                        'secret_shares': 1,
                        'secret_threshold': 1,
                    },
                    timeout=30
                )
                
                if init_response.status_code == 200:
                    init_data = init_response.json()
                    logger.info("Vault inicializado com sucesso!")
                    
                    # Salvar as chaves de unseal
                    keys = init_data.get('keys_base64', [init_data.get('keys', [])[0]])
                    root_token = init_data.get('root_token')
                    
                    logger.info("Salvando chaves de unseal...")
                    with open(self.tpm_data_dir / 'vault-unseal-keys', 'w') as f:
                        for key in keys:
                            f.write(f"{key}\n")
                    
                    if root_token:
                        with open(self.tpm_data_dir / 'vault-root-token', 'w') as f:
                            f.write(root_token)
                    
                    return True
                else:
                    logger.error(f"Erro na inicialização do Vault: {init_response.text}")
                    return False
            else:
                logger.info("Vault já está inicializado")
                return True
                
        except Exception as e:
            logger.error(f"Erro verificando inicialização do Vault: {e}")
            return False

    def unseal_vault(self):
        """Faz o unseal do Vault após validação do TPM"""
        try:
            # Verificar status do Vault
            status_response = requests.get(f"{self.vault_addr}/v1/sys/seal-status", timeout=10)
            status_data = status_response.json()
            
            if not status_data.get('sealed', True):
                logger.info("Vault já está unsealed")
                return True
            
            # Ler as chaves de unseal
            unseal_keys_file = self.tpm_data_dir / 'vault-unseal-keys'
            if not unseal_keys_file.exists():
                logger.error("Arquivo de chaves de unseal não encontrado")
                return False
            
            with open(unseal_keys_file, 'r') as f:
                keys = [line.strip() for line in f.readlines() if line.strip()]
            
            # Fazer unseal com cada chave (no nosso caso, apenas uma)
            for key in keys:
                unseal_response = requests.put(
                    f"{self.vault_addr}/v1/sys/unseal",
                    json={'key': key},
                    timeout=10
                )
                
                if unseal_response.status_code == 200:
                    unseal_data = unseal_response.json()
                    if not unseal_data.get('sealed', True):
                        logger.info("Vault unsealed com sucesso!")
                        return True
                else:
                    logger.error(f"Erro no unseal do Vault: {unseal_response.text}")
            
            logger.error("Não foi possível fazer unseal do Vault com as chaves disponíveis")
            return False
                
        except Exception as e:
            logger.error(f"Erro durante unseal do Vault: {e}")
            return False

    def run(self):
        """Fluxo principal de inicialização"""
        logger.info("Iniciando serviço de inicialização segura do Vault")
        
        # Aguardar validação do TPM
        if not self.wait_for_tpm_validation():
            logger.error("Falha na validação do TPM")
            sys.exit(1)
        
        # Inicializar Vault se necessário
        if not self.initialize_vault():
            logger.error("Falha na inicialização do Vault")
            sys.exit(1)
        
        # Fazer unseal do Vault
        if not self.unseal_vault():
            logger.error("Falha no unseal do Vault")
            sys.exit(1)
        
        logger.info("Processo de inicialização segura concluído com sucesso!")
        
        # Health check contínuo
        self.health_check()

    def health_check(self):
        """Health check contínuo do sistema"""
        while True:
            try:
                # Verificar status do Vault
                vault_status = requests.get(f"{self.vault_addr}/v1/sys/health", timeout=5)
                if vault_status.status_code == 200:
                    logger.debug("Sistema operacional normal")
                else:
                    logger.warning(f"Vault com status anormal: {vault_status.status_code}")
                
                # Verificar status do TPM
                tpm_status = requests.get(f"{self.tpm_validator_url}/status", timeout=5)
                if tpm_status.status_code == 200:
                    logger.debug("TPM validator operacional")
                else:
                    logger.warning("TPM validator com problemas")
                    
            except Exception as e:
                logger.error(f"Erro no health check: {e}")
            
            time.sleep(60)

if __name__ == "__main__":
    initializer = VaultInitializer()
    initializer.run()
