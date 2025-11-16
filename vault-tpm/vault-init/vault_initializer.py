import os
import sys
import time
import requests
import json
import base64
import subprocess
from pathlib import Path

class TPMHandler:
    """Manipula operações TPM no Alpine Linux"""
    
    def __init__(self):
        self.ready = self._check_tpm_availability()
    
    def _check_tpm_availability(self):
        """Verifica se o TPM está disponível"""
        try:
            # Verificar se dispositivo TPM existe
            if not (os.path.exists('/dev/tpm0') or os.path.exists('/dev/tpmrm0')):
                print("❌ Dispositivo TPM não encontrado")
                return False
            
            # Testar comando TPM básico
            result = subprocess.run(
                ['tpm2_getrandom', '4'], 
                capture_output=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                print("✅ TPM está disponível e respondendo")
                return True
            else:
                print(f"❌ TPM não respondeu: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao verificar TPM: {e}")
            return False
    
    def is_ready(self):
        return self.ready
    
    def encrypt(self, data):
        """Criptografa dados usando TPM no Alpine"""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            print("🔐 Criptografando com TPM...")
            
            # Abordagem para Alpine Linux
            # 1. Gerar chave temporária
            key_context = "/tmp/tpm_key.ctx"
            result = subprocess.run([
                'tpm2_createprimary', '-c', key_context,
                '-C', 'o', '-Q'
            ], capture_output=True, timeout=30)
            
            if result.returncode != 0:
                print("❌ Falha ao criar chave primária TPM")
                return self._fallback_encrypt(data)
            
            # 2. Criptografar dados
            input_file = "/tmp/tpm_input.bin"
            output_file = "/tmp/tpm_output.bin"
            
            with open(input_file, 'wb') as f:
                f.write(data)
            
            encrypt_result = subprocess.run([
                'tpm2_encryptdecrypt', '-c', key_context,
                '-o', output_file, input_file
            ], capture_output=True, timeout=30)
            
            # Limpar arquivos temporários
            for temp_file in [key_context, input_file]:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            
            if encrypt_result.returncode == 0 and os.path.exists(output_file):
                with open(output_file, 'rb') as f:
                    encrypted_data = f.read()
                os.unlink(output_file)
                
                print("✅ Dados criptografados com TPM com sucesso")
                return encrypted_data
            else:
                print(f"❌ Falha na criptografia TPM: {encrypt_result.stderr}")
                return self._fallback_encrypt(data)
                
        except Exception as e:
            print(f"❌ Erro durante criptografia TPM: {e}")
            return self._fallback_encrypt(data)
    
    def _fallback_encrypt(self, data):
        """Fallback para desenvolvimento"""
        print("⚠️  Usando criptografia fallback - APENAS DESENVOLVIMENTO")
        if isinstance(data, str):
            data = data.encode()
        return base64.b64encode(data) + b"[ALPINE-FALLBACK]"

def setup_tpm():
    """Configurar TPM no Alpine"""
    print("🔧 Inicializando TPM no Alpine Linux...")
    return TPMHandler()

def wait_for_vault(vault_url, timeout=120):
    """Aguarda o Vault ficar pronto"""
    print(f"⏳ Aguardando Vault em {vault_url}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{vault_url}/v1/sys/health", timeout=5)
            if response.status_code in [200, 501, 503]:
                print("✅ Vault está respondendo")
                return True
            else:
                print(f"📊 Vault status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            elapsed = int(time.time() - start_time)
            if elapsed > 30 and elapsed % 10 == 0:
                print(f"⏳ Aguardando Vault... ({elapsed}s)")
            time.sleep(2)
    
    print("❌ Timeout aguardando Vault")
    return False

def initialize_vault(vault_url):
    """Inicializa o Vault se necessário"""
    try:
        response = requests.get(f"{vault_url}/v1/sys/init", timeout=10)
        init_status = response.json()
        
        if not init_status.get('initialized', False):
            print("🚀 Inicializando Vault...")
            init_data = {
                "secret_shares": 5,
                "secret_threshold": 3
            }
            response = requests.put(
                f"{vault_url}/v1/sys/init", 
                json=init_data, 
                timeout=30
            )
            
            if response.status_code == 200:
                init_result = response.json()
                print("✅ Vault inicializado com sucesso")
                return init_result
            else:
                print(f"❌ Erro na inicialização: {response.status_code}")
                return None
        else:
            print("✅ Vault já está inicializado")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao verificar/inicializar Vault: {e}")
        return None

def save_encrypted_data(output_dir, init_result, tpm):
    """Salva dados criptografados"""
    if not init_result:
        print("📝 Nenhum dado para salvar - Vault já inicializado")
        return True
    
    root_token = init_result.get('root_token')
    keys_base64 = init_result.get('keys_base64', [])
    
    success = True
    
    print(f"💾 Salvando {len(keys_base64)} chaves de unseal...")
    
    # Salvar root token
    if root_token:
        encrypted_token = tpm.encrypt(root_token)
        if encrypted_token:
            token_path = os.path.join(output_dir, "root_token.enc")
            with open(token_path, 'wb') as f:
                f.write(encrypted_token)
            print(f"✅ Token root salvo em: {token_path}")
        else:
            print("❌ Falha ao criptografar root token")
            success = False
    
    # Salvar chaves de unseal
    for i, key in enumerate(keys_base64):
        encrypted_key = tpm.encrypt(key)
        if encrypted_key:
            key_path = os.path.join(output_dir, f"unseal_key_{i}.enc")
            with open(key_path, 'wb') as f:
                f.write(encrypted_key)
            print(f"✅ Chave {i} salva em: {key_path}")
        else:
            print(f"❌ Falha ao criptografar chave {i}")
            success = False
    
    return success

def main():
    print("=" * 50)
    print("🚀 Inicializador Vault com TPM - Alpine Linux")
    print("=" * 50)
    
    vault_url = os.getenv('VAULT_ADDR', 'http://vault:8200')
    output_dir = "/app/tpm-data"
    
    print(f"📍 Vault URL: {vault_url}")
    print(f"📁 Output dir: {output_dir}")
    
    # Criar diretório de saída
    os.makedirs(output_dir, exist_ok=True)
    print(f"✅ Diretório {output_dir} criado/verificado")
    
    # Verificar dispositivo TPM
    tpm_device = None
    for device in ['/dev/tpm0', '/dev/tpmrm0']:
        if os.path.exists(device):
            tpm_device = device
            print(f"✅ Dispositivo TPM encontrado: {device}")
            break
    
    if not tpm_device:
        print("❌ Nenhum dispositivo TPM encontrado")
    
    # Inicializar TPM
    tpm = setup_tpm()
    
    # Aguardar Vault
    if not wait_for_vault(vault_url):
        sys.exit(1)
    
    # Inicializar Vault
    init_result = initialize_vault(vault_url)
    
    # Salvar dados
    if init_result:
        if save_encrypted_data(output_dir, init_result, tpm):
            print("\n🎉 Processo de inicialização concluído com sucesso!")
            
            # Listar arquivos gerados
            print("\n📋 Arquivos gerados:")
            for file in sorted(Path(output_dir).iterdir()):
                size = file.stat().st_size
                print(f"   📄 {file.name} ({size} bytes)")
        else:
            print("❌ Erro ao salvar dados criptografados")
            sys.exit(1)
    else:
        print("✅ Vault já estava inicializado")

if __name__ == '__main__':
    main()
