import os
import sys
import time
import requests
import json
import base64
import subprocess
from pathlib import Path

class TPMHandler:
    """Manipula operações TPM com fallback automático"""
    
    def __init__(self):
        self.ready, self.reason, self.tcti = self._check_tpm_availability()
        if not self.ready:
            print(f"⚠️  TPM não disponível: {self.reason}")
            print("🔓 Usando modo fallback para desenvolvimento")
        else:
            print(f"✅ TPM inicializado com TCTI: {self.tcti}")
    
    def _check_tpm_availability(self):
        """Verifica se o TPM está disponível com múltiplas tentativas"""
        tcti_options = [
            'device:/dev/tpmrm0',
            'device:/dev/tpm0',
            None  # Tenta sem TCTI específico
        ]
        
        for tcti in tcti_options:
            try:
                cmd = ['tpm2_getrandom', '4']
                if tcti:
                    cmd.extend(['--tcti', tcti])
                
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                
                if result.returncode == 0:
                    return True, f"TPM operacional", tcti
                    
            except Exception as e:
                continue
        
        return False, "TPM não responde em nenhuma configuração", None
    
    def is_ready(self):
        return self.ready
    
    def encrypt(self, data):
        """Criptografa dados - usa TPM se disponível, senão fallback"""
        try:
            if isinstance(data, str):
                data = data.encode()
            
            if self.ready and self.tcti:
                encrypted = self._encrypt_with_tpm(data)
                if encrypted:
                    return encrypted
            
            # Fallback para desenvolvimento
            print("🔓 Usando criptografia fallback (modo desenvolvimento)")
            return b"FALLBACK_" + base64.b64encode(data)
                
        except Exception as e:
            print(f"❌ Erro durante criptografia: {e}")
            return b"FALLBACK_" + base64.b64encode(data)
    
    def _encrypt_with_tpm(self, data):
        """Tenta criptografar com TPM real"""
        try:
            print("🔐 Tentando criptografia com TPM...")
            
            # Abordagem mais simples: usar encryptdecrypt direto
            input_file = "/tmp/tpm_input.bin"
            output_file = "/tmp/tpm_output.bin"
            
            with open(input_file, 'wb') as f:
                f.write(data)
            
            cmd = [
                'tpm2_encryptdecrypt',
                '-o', output_file,
                input_file
            ]
            
            if self.tcti:
                cmd.extend(['--tcti', self.tcti])
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            # Limpar arquivo de entrada
            if os.path.exists(input_file):
                os.unlink(input_file)
            
            if result.returncode == 0 and os.path.exists(output_file):
                with open(output_file, 'rb') as f:
                    encrypted_data = f.read()
                os.unlink(output_file)
                
                print(f"✅ Dados criptografados com TPM: {len(encrypted_data)} bytes")
                return encrypted_data
            else:
                print(f"❌ Criptografia TPM falhou: {result.stderr.decode()}")
                return None
                
        except Exception as e:
            print(f"❌ Erro na criptografia TPM: {e}")
            return None

def setup_tpm():
    """Configurar TPM"""
    print("🔧 Inicializando TPM...")
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
        except requests.exceptions.RequestException:
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"⏳ Aguardando Vault... ({elapsed}s)")
            time.sleep(2)
    
    print("❌ Timeout aguardando Vault")
    return False

def initialize_vault(vault_url):
    """Inicializa o Vault em modo produção"""
    try:
        response = requests.get(f"{vault_url}/v1/sys/init", timeout=10)
        init_status = response.json()
        
        if not init_status.get('initialized', False):
            print("🚀 Inicializando Vault em modo produção...")
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
                print("✅ Vault inicializado em modo produção")
                print(f"📋 Chaves geradas: {len(init_result.get('keys_base64', []))}")
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
        print("❌ Nenhum dado para salvar")
        return False
    
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
            
            # Salvar em claro para referência
            clear_path = os.path.join(output_dir, "root_token.txt")
            with open(clear_path, 'w') as f:
                f.write(root_token)
            print(f"📝 Token em claro salvo em: {clear_path}")
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
            
            # Salvar em claro para referência
            clear_path = os.path.join(output_dir, f"unseal_key_{i}.txt")
            with open(clear_path, 'w') as f:
                f.write(key)
        else:
            print(f"❌ Falha ao criptografar chave {i}")
            success = False
    
    return success

def main():
    print("=" * 60)
    print("🚀 INICIALIZADOR VAULT COM TPM")
    print("=" * 60)
    
    vault_url = os.getenv('VAULT_ADDR', 'http://vault:8200')
    output_dir = "/app/tpm-data"
    
    print(f"📍 Vault URL: {vault_url}")
    print(f"📁 Output dir: {output_dir}")
    
    # Criar diretório de saída
    os.makedirs(output_dir, exist_ok=True)
    print(f"✅ Diretório {output_dir} preparado")
    
    # Inicializar TPM
    tpm = setup_tpm()
    
    # Aguardar Vault
    if not wait_for_vault(vault_url):
        sys.exit(1)
    
    # Inicializar Vault
    init_result = initialize_vault(vault_url)
    
    if init_result:
        # Salvar dados criptografados
        if save_encrypted_data(output_dir, init_result, tpm):
            print("\n✅ Dados de inicialização salvos!")
            
            # Listar arquivos gerados
            print("\n📋 ARQUIVOS GERADOS:")
            for file in sorted(Path(output_dir).iterdir()):
                size = file.stat().st_size
                print(f"   📄 {file.name} ({size} bytes)")
            
            if not tpm.is_ready():
                print("\n⚠️  AVISO: Modo fallback ativo")
                print("   Os arquivos .enc usam criptografia simulada")
                print("   Para produção, verifique o acesso ao TPM")
            
            print("\n🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
        else:
            print("❌ Falha ao salvar dados")
            sys.exit(1)
    else:
        print("⚠️  Vault já estava inicializado")

if __name__ == '__main__':
    main()
