import os
import time
import subprocess
from pathlib import Path

def check_tpm_status():
    """Verifica status do TPM usando /dev/tpmrm0"""
    try:
        # Verificar se dispositivo TPM existe
        if not os.path.exists('/dev/tpmrm0'):
            return False, "❌ Dispositivo /dev/tpmrm0 não encontrado"
        
        # Testar comando básico do TPM com TCTI específico
        result = subprocess.run(
            ['tpm2_getrandom', '4', '--tcti', 'device:/dev/tpmrm0'], 
            capture_output=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            return True, "✅ TPM operacional com /dev/tpmrm0"
        else:
            return False, f"❌ TPM não responde: {result.stderr.decode()}"
            
    except Exception as e:
        return False, f"❌ Erro TPM: {e}"

def check_encrypted_files():
    """Verifica se arquivos .enc existem e são válidos"""
    data_dir = Path("/app/tpm-data")
    if not data_dir.exists():
        return False, "❌ Diretório de dados não existe"
    
    enc_files = list(data_dir.glob("*.enc"))
    if not enc_files:
        return False, "❌ Nenhum arquivo .enc encontrado"
    
    # Verificar se arquivos têm conteúdo
    empty_files = []
    valid_files = []
    
    for file in enc_files:
        if file.stat().st_size == 0:
            empty_files.append(file.name)
        else:
            valid_files.append(file.name)
    
    if empty_files:
        return False, f"❌ Arquivos vazios: {', '.join(empty_files)}"
    
    # Verificar se são arquivos TPM reais (não simulados)
    for file in enc_files:
        with open(file, 'rb') as f:
            content = f.read(100)
            if content.startswith(b"SIMULATED_TPM_"):
                return False, f"❌ Arquivo {file.name} usa criptografia simulada"
    
    return True, f"✅ {len(valid_files)} arquivos .enc válidos (TPM real)"

def check_vault_status():
    """Verifica se Vault está acessível e unsealed"""
    try:
        import requests
        response = requests.get('http://vault:8200/v1/sys/health', timeout=5)
        if response.status_code == 200:
            return True, "✅ Vault está operacional e unsealed"
        elif response.status_code == 503:
            return False, "❌ Vault está sealed"
        elif response.status_code == 501:
            return False, "❌ Vault não inicializado"
        else:
            return False, f"❌ Vault status inesperado: {response.status_code}"
    except Exception as e:
        return False, f"❌ Vault não acessível: {e}"

def check_vault_operations():
    """Testa operações básicas do Vault"""
    try:
        import requests
        
        # Verificar se a API responde
        response = requests.get('http://vault:8200/v1/sys/auth', timeout=5)
        
        if response.status_code == 200:
            return True, "✅ API do Vault operacional"
        elif response.status_code == 403:
            return True, "✅ Vault responde (sem token)"
        else:
            return False, f"❌ Falha na API: {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Erro nas operações: {e}"

def main():
    print("=" * 50)
    print("🔍 TPM VALIDATOR - MODO PRODUÇÃO (/dev/tpmrm0)")
    print("=" * 50)
    
    check_count = 0
    
    while True:
        check_count += 1
        print(f"\n📊 Verificação #{check_count}")
        print("-" * 50)
        
        # Verificar TPM
        tpm_ok, tpm_msg = check_tpm_status()
        print(f"🔧 TPM: {tpm_msg}")
        
        # Verificar arquivos
        files_ok, files_msg = check_encrypted_files()
        print(f"📁 Arquivos: {files_msg}")
        
        # Verificar Vault
        vault_ok, vault_msg = check_vault_status()
        print(f"🚀 Vault: {vault_msg}")
        
        # Verificar operações
        operations_ok, operations_msg = check_vault_operations()
        print(f"⚡ Operações: {operations_msg}")
        
        # Status geral
        all_ok = all([tpm_ok, files_ok, vault_ok, operations_ok])
        
        if all_ok:
            print("\n🎉 STATUS: Sistema 100% operacional em produção!")
        else:
            print("\n⚠️  STATUS: Problemas detectados")
            if not tpm_ok:
                print("   ❌ TPM com problemas")
            if not files_ok:
                print("   ❌ Arquivos criptografados com problemas")
            if not vault_ok:
                print("   ❌ Vault com problemas")
            if not operations_ok:
                print("   ❌ Operações com problemas")
        
        print(f"⏰ Próxima verificação em 30 segundos...")
        time.sleep(30)

if __name__ == '__main__':
    main()
