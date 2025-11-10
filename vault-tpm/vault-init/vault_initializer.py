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
        self.max_retries = 60
        self.retry_delay = 5
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

    def check_vault_status(self):
        """Verifica o status do Vault de forma simples"""
        try:
            response = requests.get(f"{self.vault_addr}/v1/sys/health", timeout=5)
            logger.info(f"Vault status: {response.status_code}")
            return True
        except Exception as e:
            logger.warning(f"Vault não está pronto: {e}")
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
        
        logger.info("✅ Processo de inicialização segura concluído com sucesso!")
        
        # Health check contínuo
        while True:
            try:
                # Verificar status do sistema
                vault_ok = self.check_vault_status()
                tpm_ok = requests.get(f"{self.tpm_validator_url}/status", timeout=5).status_code == 200
                
                if vault_ok and tpm_ok:
                    logger.info("✅ Sistema operacional normal")
                else:
                    logger.warning("⚠️ Problemas detectados no sistema")
                    
            except Exception as e:
                logger.error(f"❌ Erro no health check: {e}")
            
            time.sleep(30)

if __name__ == "__main__":
    initializer = VaultInitializer()
    initializer.run()
