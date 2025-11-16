import os
import time
import subprocess
from pathlib import Path

def check_tpm_status():
    """Verifica status do TPM no Alpine"""
    try:
        # Verificar se dispositivo TPM existe
        if not (os.path.exists('/dev/tpm0') or os.path.exists('/dev/tpmrm0')):
            return False, "❌ Dispositivo TPM não encontrado"
        
        # Testar comando básico do TPM
        result = subprocess.run(
            ['tpm2_getrandom', '4'], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            return True, "✅ TPM operacional"
        else:
            return False, f"❌ TPM não responde: {result.stderr}"
            
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
    for file in enc_files:
        if file.stat().st_size == 0:
            empty_files.append(file.name)
    
    if empty_files:
        return False, f"❌ Arquivos vazios: {', '.join(empty_files)}"
    
    return True, f"✅ {len(enc_files)} arquivos .enc válidos"

def check_vault_status():
    """Verifica se Vault está acessível"""
    try:
        import requests
        response = requests.get('http://vault:8200/v1/sys/health', timeout=5)
        if response.status_code in [200, 501, 503]:
            return True, "✅ Vault está respondendo"
        else:
            return False, f"❌ Vault status: {response.status_code}"
    except Exception as e:
        return False, f"❌ Vault não acessível: {e}"

def main():
    print("=" * 40)
    print("🔍 TPM Validator - Alpine Linux")
    print("=" * 40)
    
    check_count = 0
    
    while True:
        check_count += 1
        print(f"\n📊 Verificação #{check_count}")
        print("-" * 30)
        
        # Verificar TPM
        tpm_ok, tpm_msg = check_tpm_status()
        print(f"TPM: {tpm_msg}")
        
        # Verificar arquivos
        files_ok, files_msg = check_encrypted_files()
        print(f"Arquivos: {files_msg}")
        
        # Verificar Vault
        vault_ok, vault_msg = check_vault_status()
        print(f"Vault: {vault_msg}")
        
        # Status geral
        if all([tpm_ok, files_ok, vault_ok]):
            print("\n🎉 STATUS: Sistema completo operacional!")
        else:
            print("\n⚠️  STATUS: Problemas detectados")
        
        print(f"⏰ Próxima verificação em 30 segundos...")
        time.sleep(30)

if __name__ == '__main__':
    main()
