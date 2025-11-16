import os
import time
import subprocess
from pathlib import Path
from flask import Flask, jsonify
import threading
import requests

app = Flask(__name__)

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        # Verificar TPM
        tpm_result = subprocess.run(['tpm2_getrandom', '4', '--tcti', 'device:/dev/tpmrm0'], capture_output=True, timeout=10)
        tpm_ok = tpm_result.returncode == 0
        
        # Verificar arquivos
        data_dir = Path("/app/tpm-data")
        enc_files = list(data_dir.glob("*.enc"))
        files_ok = len(enc_files) > 0
        
        status = "healthy" if (tpm_ok and files_ok) else "unhealthy"
        
        return jsonify({
            "status": status,
            "tpm_operational": tpm_ok,
            "encrypted_files_present": files_ok,
            "files_count": len(enc_files),
            "service": "tpm-validator"
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_health_check():
    """Executa o servidor de health check"""
    print("🏥 Iniciando servidor de health check na porta 8080...")
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def check_tpm_status():
    """Verifica status do TPM"""
    try:
        result = subprocess.run(['tpm2_getrandom', '4', '--tcti', 'device:/dev/tpmrm0'], capture_output=True, timeout=10)
        if result.returncode == 0:
            return True, "✅ TPM operacional"
        else:
            return False, f"❌ TPM não responde: {result.stderr.decode()}"
    except Exception as e:
        return False, f"❌ Erro TPM: {e}"

def check_files():
    """Verifica arquivos .enc"""
    data_dir = Path("/app/tpm-data")
    if not data_dir.exists():
        return False, "❌ Diretório não existe"
    
    enc_files = list(data_dir.glob("*.enc"))
    if not enc_files:
        return False, "❌ Nenhum arquivo .enc"
    
    return True, f"✅ {len(enc_files)} arquivos .enc encontrados"

def check_vault():
    """Verifica status do Vault"""
    try:
        response = requests.get('http://vault:8200/v1/sys/health', timeout=5)
        if response.status_code in [200, 501, 503]:
            return True, "✅ Vault respondendo"
        else:
            return False, f"❌ Vault status: {response.status_code}"
    except Exception as e:
        return False, f"❌ Vault inacessível: {e}"

def main():
    # Iniciar health check em thread separada
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    
    print("🔍 TPM VALIDATOR COM HEALTH CHECK")
    print("================================")
    
    check_count = 0
    
    while True:
        check_count += 1
        print(f"\n📊 Verificação #{check_count} - {time.strftime('%H:%M:%S')}")
        print("-" * 40)
        
        # Verificar TPM
        tpm_ok, tpm_msg = check_tpm_status()
        print(f"🔧 TPM: {tpm_msg}")
        
        # Verificar arquivos
        files_ok, files_msg = check_files()
        print(f"📁 Arquivos: {files_msg}")
        
        # Verificar Vault
        vault_ok, vault_msg = check_vault()
        print(f"🚀 Vault: {vault_msg}")
        
        # Status geral
        if all([tpm_ok, files_ok, vault_ok]):
            print("\n🎉 STATUS: Sistema 100% operacional!")
        else:
            print("\n⚠️  STATUS: Problemas detectados")
            if not tpm_ok:
                print("   ❌ TPM com problemas")
            if not files_ok:
                print("   ❌ Arquivos criptografados com problemas")
            if not vault_ok:
                print("   ❌ Vault com problemas")
        
        print("⏰ Próxima verificação em 30 segundos...")
        time.sleep(30)

if __name__ == '__main__':
    main()
