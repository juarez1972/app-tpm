from flask import Flask, jsonify
import hashlib
import os
from datetime import datetime

app = Flask(__name__)

def read_tpm_secret():
    """Lê o segredo do TPM"""
    try:
        with open('/app/tpm-data/secret', 'rb') as f:
            return f.read()
    except Exception as e:
        return None

def validate_tpm():
    """Valida o TPM verificando o segredo"""
    secret = read_tpm_secret()
    if secret is None:
        return False, "Não foi possível ler o segredo do TPM"
    
    if len(secret) != 32:
        return False, f"Segredo com tamanho inválido: {len(secret)} bytes (esperado: 32)"
    
    return True, "TPM validado com sucesso"

@app.route('/')
def index():
    """Página principal"""
    validated, message = validate_tpm()
    status = "✅ VALIDADO" if validated else "❌ FALHA"
    
    return f"""
    <html>
        <head><title>Sistema TPM + Vault</title></head>
        <body>
            <h1>Sistema de Validação TPM + Vault</h1>
            <h2>Status: {status}</h2>
            <p><strong>Mensagem:</strong> {message}</p>
            <p><strong>Endpoints:</strong></p>
            <ul>
                <li><a href="/status">/status</a> - Status JSON da validação</li>
                <li><a href="/health">/health</a> - Health check simples</li>
            </ul>
        </body>
    </html>
    """

@app.route('/status')
def status():
    """Endpoint para verificar o status da validação TPM"""
    validated, message = validate_tpm()
    
    # Calcular hash do segredo para verificação
    secret = read_tpm_secret()
    secret_hash = hashlib.sha256(secret).hexdigest() if secret else None
    
    return jsonify({
        'tpm_validated': validated,
        'message': message,
        'secret_hash': secret_hash,
        'secret_length': len(secret) if secret else 0,
        'machine_verified': validated,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    """Health check simples"""
    return jsonify({'status': 'healthy', 'service': 'tpm-validator'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
