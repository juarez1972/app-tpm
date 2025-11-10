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
        self.max_retries = 60  # Aumentei para 60 tentativas
        self.retry_delay = 5   # 5 segundos entre tentativas
        self.tpm_data_dir = Path('/app/tpm-data')

    def wait_for_service(self, url, service_name):
        """Aguarda um serviço ficar disponível"""
        logger.info(f"Aguardando {service_name} ficar disponível...")
        
        for i in range(self.max_retries):
            try:
                response = requests.get(url, timeout=5)
                logger.info(f"{service_name} está respondendo!")
                return True
            except requests.exceptions.ConnectionError:
                if i < self.max_retries - 1:
                    logger.info(f"{service_name} não está pronto... Tentativa {i+1}/{self.max_retries}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"{service_name} não ficou pronto a tempo")
                    return False
            except Exception as e:
                logger.warning(f"Erro ao conectar com {service_name}: {e}")
                if i < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return False

    def wait_for_tpm_validation(self):
        """Aguarda a validação do TPM"""
        logger.info("Aguardando validação do TPM...")
        
        for i in range(self.max_retries):
            try:
                response = requests.get(f"{self.tpm_validator_url}/status", timeout=10)
                if response.status_code == 200:
                    status_data = response.json()
                    logger.info(f"Resposta do TPM validator: {status_data}")
                    
                    if status_data.get('tpm_validated'):
                        logger.info("TPM validado com sucesso!")
                        return True
                    else:
                        logger.info(f"TPM ainda não validado: {status_data.get('message')}")
                else:
                    logger.warning(f"Resposta inesperada do validador TPM: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro ao conectar com validador TPM: {e}")
            
            if i < self.max_retries - 1:
                logger.info(f"Tentativa {i+1}/{self.max_retries} - Aguardando {self.retry_delay} segundos...")
                time.sleep(self.retry_delay)
        
        logger.error("Timeout aguardando validação do TPM")
        return False

    def initialize_vault(self):
    """Inicializa o Vault se necessário"""
    try:
        # Verificar se o Vault já está inicializado
        response = requests.get(f"{self.vault_addr}/v1/sys/health", timeout=10)
        
        # Status 501 = não inicializado, 503 = sealed, 200 = ok
        if response.status_code == 501:
            logger.info("Inicializando Vault em modo produção...")
            
            init_response = requests.put(
                f"{self.vault_addr}/v1/sys/init",
                json={
                    'secret_shares': 1,
                    'secret_threshold': 1
                },
                timeout=30
            )
            
            if init_response.status_code == 200:
                init_data = init_response.json()
                logger.info("Vault inicializado com sucesso!")
                
                # Salvar as chaves de unseal
                keys = init_data.get('keys_base64', init_data.get('keys', []))
                root_token = init_data.get('root_token')
                
                if keys:
                    with open(self.tpm_data_dir / 'vault-unseal-keys', 'w') as f:
                        for key in keys:
                            f.write(f"{key}\n")
                    logger.info(f"Salvas {len(keys)} chaves de unseal")
                
                if root_token:
                    with open(self.tpm_data_dir / 'vault-root-token', 'w') as f:
                        f.write(root_token)
                    logger.info("Token root salvo")
                
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
        """Faz o unseal do Vault"""
        try:
            # Verificar status
            status_response = requests.get(f"{self.vault_addr}/v1/sys/seal-status", timeout=10)
            status_data = status_response.json()
            
            if not status_data.get('sealed', True):
                logger.info("Vault já está unsealed")
                return True
            
            # Tentar usar chaves salvas
            unseal_keys_file = self.tpm_data_dir / 'vault-unseal-keys'
            if unseal_keys_file.exists():
                with open(unseal_keys_file, 'r') as f:
                    keys = [line.strip() for line in f.readlines() if line.strip()]
                
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
            
            logger.error("Não foi possível fazer unseal do Vault")
            return False
                
        except Exception as e:
            logger.error(f"Erro durante unseal do Vault: {e}")
            return False

    def run(self):
        """Fluxo principal de inicialização"""
        logger.info("Iniciando serviço de inicialização segura do Vault")
        
        # PRIMEIRO: Aguardar Vault ficar pronto
        if not self.wait_for_service(f"{self.vault_addr}/v1/sys/health", "Vault"):
            logger.error("Falha ao conectar com Vault")
            sys.exit(1)
        
        # SEGUNDO: Aguardar validação do TPM
        if not self.wait_for_tpm_validation():
            logger.error("Falha na validação do TPM")
            sys.exit(1)
        
        # TERCEIRO: Inicializar Vault se necessário
        if not self.initialize_vault():
            logger.error("Falha na inicialização do Vault")
            sys.exit(1)
        
        # QUARTO: Fazer unseal do Vault
        if not self.unseal_vault():
            logger.error("Falha no unseal do Vault")
            sys.exit(1)
        
        logger.info("✅ Processo de inicialização segura concluído com sucesso!")
        
        # Health check contínuo
        while True:
            try:
                # Verificar status do sistema
                vault_health = requests.get(f"{self.vault_addr}/v1/sys/health", timeout=5)
                tpm_status = requests.get(f"{self.tpm_validator_url}/status", timeout=5)
                
                if vault_health.status_code == 200 and tpm_status.status_code == 200:
                    logger.debug("Sistema operacional normal")
                else:
                    logger.warning("Problemas detectados no sistema")
                    
            except Exception as e:
                logger.error(f"Erro no health check: {e}")
            
            time.sleep(30)  # Verifica a cada 30 segundos

if __name__ == "__main__":
    initializer = VaultInitializer()
    initializer.run()
