
from flask import Flask, jsonify
import subprocess
import sys
import logging
import os
from tpm2_pytss import TSS2_Exception, TCTI, TPM2

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def unseal_secret_from_tpm():
    """
    Tenta deslacrar um segredo usando o TPM.
    Retorna True em caso de sucesso, False caso contrário.
    """
    sealed_context_path = "sealed.ctx"
    logging.info(f"Tentando deslacrar o segredo do TPM usando o contexto: {sealed_context_path}")
    
    try:
        # Executa o comando tpm2_unseal para decifrar o segredo
        # O resultado (o segredo) é capturado, mas não usado aqui, apenas verificamos o sucesso
        result = subprocess.run(
            ["tpm2_unseal", "-c", sealed_context_path],
            capture_output=True,
            text=True,
            check=True  # Lança uma exceção se o comando retornar um código de erro
        )
        logging.info("Sucesso! Segredo deslacrado do TPM. A inicialização da aplicação está autorizada.")
        # Em um cenário real, você usaria o segredo: secret = result.stdout.strip()
        return True
    except FileNotFoundError:
        logging.error("Erro: O comando 'tpm2_unseal' não foi encontrado. Verifique se tpm2-tools está instalado no contêiner.")
        return False
    except subprocess.CalledProcessError as e:
        logging.error("FALHA NA AUTENTICAÇÃO DO TPM: Não foi possível deslacrar o segredo.")
        logging.error(f"Código de retorno: {e.returncode}")
        logging.error(f"Stderr: {e.stderr.strip()}")
        return False
    except Exception as e:
        logging.error(f"Ocorreu um erro inesperado durante a operação de deslacramento: {e}")
        return False

# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    if not unseal_secret_from_tpm():
        logging.critical("A verificação do TPM falhou. A aplicação será encerrada.")
        sys.exit(1) # Encerra com código de erro

    app = Flask(__name__)

    @app.route('/')
    def home():
        return "Hello, World! A aplicação está rodando após a verificação bem-sucedida do TPM."

    app.run(host='0.0.0.0', port=5000)

@app.route('/status')
def status():
    try:
        # Tenta inicializar comunicação com TPM
        tcti = TCTI.load("tcti-device")
        tpm = TPM2(tcti=tcti)

        # Testa comunicação básica com TPM
        tpm.startup(TPM2_SU.CLEAR)

        return jsonify({
            'tpm_validated': True,
            'machine_verified': True,
            'timestamp': '2024-11-09T22:15:00Z'
        })
    except Exception as e:
        return jsonify({
            'tpm_validated': False,
            'error': str(e),
            'timestamp': '2024-11-09T22:15:00Z'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
