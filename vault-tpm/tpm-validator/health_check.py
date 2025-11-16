from flask import Flask, jsonify
import subprocess
import os
from pathlib import Path

app = Flask(__name__)

def check_tpm_basic():
    """Verifica operação básica do TPM"""
    try:
        result = subprocess.run(
            ['tpm2_getrandom', '4'], 
            capture_output=True, 
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def check_encrypted_files():
    """Verifica se arquivos .enc existem"""
    data_dir = Path("/app/tpm-data")
    return data_dir.exists() and any(data_dir.glob("*.enc"))

@app.route('/health')
def health_check():
    """Endpoint de health check"""
    tpm_ok = check_tpm_basic()
    files_ok = check_encrypted_files()
    
    status = "healthy" if (tpm_ok and files_ok) else "unhealthy"
    
    return jsonify({
        "status": status,
        "tpm_operational": tpm_ok,
        "encrypted_files_present": files_ok,
        "service": "tpm-validator"
    })

@app.route('/metrics')
def metrics():
    """Endpoint de métricas para Prometheus"""
    from datetime import datetime
    data_dir = Path("/app/tpm-data")
    enc_files = list(data_dir.glob("*.enc"))
    
    metrics_data = {
        "tpm_validator_files_count": len(enc_files),
        "tpm_validator_last_check": datetime.now().timestamp(),
        "tpm_validator_status": 1 if check_tpm_basic() else 0
    }
    
    return jsonify(metrics_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
