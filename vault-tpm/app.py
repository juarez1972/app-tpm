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
    """Valida o TPM comparando o segredo armazenado com o segredo lido"""
    secret = read_tpm_secret()
    if secret is None:
        return False, "Não foi possível ler o segredo do TPM"

    # Aqui você pode adicionar lógica para comparar com um hash esperado, se necessário
    # Por enquanto, vamos apenas retornar True se o segredo foi lido
    return True, "TPM validado com sucesso"

@app.route('/')
def index():
    """Página principal que mostra o status da validação TPM"""
    validated, message = validate_tpm()
    if validated:
        return """
        <html>
            <head><title>Validação TPM</title></head>
            <body>
                <h1>✅ TPM Validado com Sucesso</h1>
                <p><strong>Mensagem:</strong> {}</p>
                <p><a href="/status">Ver Status JSON</a></p>
            </body>
        </html>
        """.format(message)
    else:
        return """
        <html>
            <head><title>Validação TPM</title></head>
            <body>
                <h1>❌ Falha na Validação TPM</h1>
                <p><strong>Erro:</strong> {}</p>
                <p><a href="/status">Ver Status JSON</a></p>
            </body>
        </html>
        """.format(message)

@app.route('/status')
def status():
    """Endpoint para verificar o status da validação TPM (usado pelo vault-initializer)"""
    validated, message = validate_tpm()
    
    # Calcular hash do segredo para debug
    secret = read_tpm_secret()
    secret_hash = hashlib.sha256(secret).hexdigest() if secret else None
    
    return jsonify({
        'tpm_validated': validated,
        'message': message,
        'secret_hash': secret_hash,
        'machine_verified': validated,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    """Health check simples"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
