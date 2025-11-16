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

    def check_port_available(self):
        """Verifica se a porta do Vault está disponível"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', 8200))
            sock.close()
            return True
        except socket.error:
            logger.error("❌ Porta 8200 já está em uso!")
            return False

    def get_vault_token(self):
        """Obtém o token do Vault do arquivo vault-root-token"""
        token_file = self.tpm_data_dir / 'vault-root-token'
        try:
            if token_file.exists():
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                if token:
                    logger.info(f"Token do Vault carregado: {token[:8]}...")
                    return token
        except Exception as e:
            logger.warning(f"Erro ao ler token do Vault: {e}")
        
        # Fallback para token padrão de desenvolvimento
        logger.info("Usando token padrão de desenvolvimento")
        return 'temp-root-token'

    def wait_for_service(self, url, service_name, timeout=5):
        """Aguarda um serviço ficar disponível"""
        logger.info(f"Aguardando {service_name} ficar disponível...")
        
        for i in range(self.max_retries):
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    logger.info(f"✅ {service_name} está respondendo!")
                    return True
                else:
                    logger.info(f"{service_name} retornou status: {response.status_code}")
            except requests.exceptions.ConnectionError:
                if i < self.max_retries - 1:
                    if i % 10 == 0:  # Log a cada 10 tentativas
                        logger.info(f"{service_name} não está pronto... Tentativa {i+1}/{self.max_retries}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ {service_name} não ficou pronto a tempo")
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
                    
                    if status_data.get('tpm_validated'):
                        logger.info("✅ TPM validado com sucesso!")
                        return True
                    else:
                        if i % 10 == 0:  # Log a cada 10 tentativas
                            logger.info(f"TPM ainda não validado: {status_data.get('message')}")
                else:
                    if i % 10 == 0:
                        logger.warning(f"Resposta inesperada do TPM validator: {response.status_code}")
            except requests.exceptions.RequestException as e:
                if i % 10 == 0:
                    logger.warning(f"Erro ao conectar com TPM validator: {e}")
            
            if i < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error("❌ Timeout aguardando validação do TPM")
        return False

    def check_vault_health(self):
        """Verifica a saúde do Vault"""
        try:
            token = self.get_vault_token()
            response = requests.get(
                f"{self.vault_addr}/v1/sys/health",
                headers={'X-Vault-Token': token},
                timeout=5
            )
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Vault health: initialized={health_data.get('initialized')}, sealed={health_data.get('sealed')}")
                return True
            else:
                logger.warning(f"Vault health check falhou: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Erro ao verificar saúde do Vault: {e}")
            return False

    def test_vault_operations(self):
        """Testa operações de escrita e leitura no Vault"""
        try:
            token = self.get_vault_token()
            
            # Escrever um secret de teste
            write_response = requests.post(
                f"{self.vault_addr}/v1/secret/data/health-check",
                headers={'X-Vault-Token': token},
                json={'data': {'status': 'healthy', 'timestamp': time.time()}},
                timeout=10
            )
            
            if write_response.status_code not in [200, 204]:
                logger.warning(f"Falha ao escrever no Vault: {write_response.status_code}")
                return False
            
            # Ler o secret de teste
            read_response = requests.get(
                f"{self.vault_addr}/v1/secret/data/health-check",
                headers={'X-Vault-Token': token},
                timeout=10
            )
            
            if read_response.status_code == 200:
                logger.info("✅ Operações de escrita/leitura no Vault funcionando")
                return True
            else:
                logger.warning(f"Falha ao ler do Vault: {read_response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Erro ao testar operações do Vault: {e}")
            return False

    def run(self):
        """Fluxo principal de inicialização"""
        logger.info("🚀 Iniciando serviço de inicialização segura do Vault")
        
        # PRIMEIRO: Aguardar Vault ficar pronto
        if not self.wait_for_service(f"{self.vault_addr}/v1/sys/health", "Vault"):
            logger.error("❌ Falha ao conectar com Vault")
            sys.exit(1)
        
        # SEGUNDO: Aguardar validação do TPM
        if not self.wait_for_tpm_validation():
            logger.error("❌ Falha na validação do TPM")
            sys.exit(1)
        
        # TERCEIRO: Verificar saúde do Vault
        if not self.check_vault_health():
            logger.error("❌ Problema na saúde do Vault")
            sys.exit(1)
        
        # QUARTO: Testar operações do Vault
        if not self.test_vault_operations():
            logger.warning("⚠️ Operações do Vault com problemas, mas continuando...")
        
        token = self.get_vault_token()
        logger.info(f"🎉 Processo de inicialização segura concluído! Token: {token}")
        
        # Health check contínuo
        success_count = 0
        while True:
            try:
                vault_ok = self.check_vault_health()
                tpm_response = requests.get(f"{self.tpm_validator_url}/status", timeout=5)
                tpm_ok = tpm_response.status_code == 200 and tpm_response.json().get('tpm_validated', False)
                
                if vault_ok and tpm_ok:
                    success_count += 1
                    if success_count % 12 == 0:  # Log a cada 6 minutos (12 * 30s)
                        logger.info(f"✅ Sistema operacional normal - {success_count} checks bem-sucedidos")
                else:
                    logger.warning("⚠️ Problemas detectados no sistema")
                    success_count = 0
                    
            except Exception as e:
                logger.error(f"❌ Erro no health check: {e}")
                success_count = 0
            
            time.sleep(30)  # Verificar a cada 30 segundos

if __name__ == "__main__":
    initializer = VaultInitializer()
    initializer.run()
