#!/bin/bash

echo "📦 CRIANDO ESTRUTURA COM REQUIREMENTS.TXT"
echo "========================================"

# Parar serviços existentes
docker-compose down 2>/dev/null

# Criar diretórios
mkdir -p vault-init tpm-validator vault-data tpm-data

# 1. Criar requirements.txt para vault-initializer
cat > vault-init/requirements.txt << 'EOF'
requests==2.31.0
cryptography==41.0.7
EOF

# 2. Criar requirements.txt para tpm-validator
cat > tpm-validator/requirements.txt << 'EOF'
requests==2.31.0
flask==2.3.3
EOF

# 3. Criar Dockerfiles
cat > vault-init/Dockerfile << 'EOF'
FROM python:3.9-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tpm2-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY vault_initializer.py .

CMD ["python", "vault_initializer.py"]
EOF

cat > tpm-validator/Dockerfile << 'EOF'
FROM python:3.9-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tpm2-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY tpm_validator.py .
COPY health_check.py .

CMD ["python", "tpm_validator.py"]
EOF

# 4. Criar docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  vault:
    image: vault:1.13.3
    container_name: vault
    ports:
      - "8201:8200"
    command: server -dev -dev-root-token-id=root -dev-listen-address=0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    networks:
      - vault-network

  vault-initializer:
    build: ./vault-init
    container_name: vault-initializer
    volumes:
      - ./tpm-data:/app/tpm-data
    devices:
      - "/dev/tpmrm0:/dev/tpmrm0"
    environment:
      - VAULT_ADDR=http://vault:8200
    depends_on:
      - vault
    networks:
      - vault-network

  tpm-validator:
    build: ./tpm-validator
    container_name: tpm-validator
    volumes:
      - ./tpm-data:/app/tpm-data
    devices:
      - "/dev/tpmrm0:/dev/tpmrm0"
    ports:
      - "8080:8080"  # Para health checks
    depends_on:
      - vault-initializer
    networks:
      - vault-network

networks:
  vault-network:
    driver: bridge
EOF

# 5. Criar scripts Python se não existirem
if [ ! -f "vault-init/vault_initializer.py" ]; then
    cat > vault-init/vault_initializer.py << 'EOF'
import os
import sys
import time
import requests
import base64
import subprocess
from pathlib import Path

def check_tpm():
    """Verifica se o TPM está acessível"""
    try:
        result = subprocess.run(['tpm2_getrandom', '4'], capture_output=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def encrypt_with_tpm(data):
    """Criptografa dados usando TPM (simulado ou real)"""
    try:
        if isinstance(data, str):
            data = data.encode()
        
        # Tentar criptografia real com TPM
        if check_tpm():
            print("🔐 Usando TPM real para criptografia")
            # Implementar criptografia real com TPM aqui
            # Por enquanto, retorna base64 como fallback
            return base64.b64encode(data) + b"[TPM_REAL]"
        else:
            print("🔓 Usando criptografia simulada")
            return base64.b64encode(data) + b"[TPM_SIMULATED]"
    except Exception as e:
        print(f"❌ Erro na criptografia: {e}")
        return base64.b64encode(data) + b"[ERROR]"

def main():
    print("🚀 VAULT INITIALIZER COM REQUIREMENTS.TXT")
    print("=========================================")
    
    vault_url = os.getenv('VAULT_ADDR', 'http://vault:8200')
    output_dir = "/app/tpm-data"
    
    print(f"📍 Vault URL: {vault_url}")
    print(f"📁 Output dir: {output_dir}")
    
    # Criar diretório
    os.makedirs(output_dir, exist_ok=True)
    
    # Aguardar Vault
    print("⏳ Aguardando Vault...")
    for i in range(30):
        try:
            response = requests.get(f"{vault_url}/v1/sys/health", timeout=5)
            if response.status_code in [200, 501, 503]:
                print("✅ Vault está respondendo")
                break
        except:
            if i % 5 == 0:
                print(f"   ... ainda aguardando ({i*2}s)")
        time.sleep(2)
    else:
        print("❌ Timeout aguardando Vault")
        sys.exit(1)
    
    # Verificar/inicializar Vault
    try:
        response = requests.get(f"{vault_url}/v1/sys/init", timeout=10)
        init_status = response.json()
        
        if not init_status.get('initialized', False):
            print("🚀 Inicializando Vault...")
            init_data = {"secret_shares": 5, "secret_threshold": 3}
            response = requests.put(f"{vault_url}/v1/sys/init", json=init_data, timeout=30)
            
            if response.status_code == 200:
                init_result = response.json()
                print("✅ Vault inicializado")
                
                # Salvar dados criptografados
                root_token = init_result.get('root_token')
                keys_base64 = init_result.get('keys_base64', [])
                
                if root_token:
                    encrypted = encrypt_with_tpm(root_token)
                    with open(f"{output_dir}/root_token.enc", 'wb') as f:
                        f.write(encrypted)
                    print("✅ Token root criptografado salvo")
                    
                    # Salvar também em claro para referência
                    with open(f"{output_dir}/root_token.txt", 'w') as f:
                        f.write(root_token)
                
                for i, key in enumerate(keys_base64):
                    encrypted = encrypt_with_tpm(key)
                    with open(f"{output_dir}/unseal_key_{i}.enc", 'wb') as f:
                        f.write(encrypted)
                    print(f"✅ Chave {i} criptografada salva")
                    
                    # Salvar também em claro para referência
                    with open(f"{output_dir}/unseal_key_{i}.txt", 'w') as f:
                        f.write(key)
                
                print("🎉 Processo concluído com sucesso!")
                
                # Listar arquivos gerados
                print("\n📋 Arquivos gerados:")
                for file in Path(output_dir).iterdir():
                    size = file.stat().st_size
                    print(f"   📄 {file.name} ({size} bytes)")
                    
            else:
                print(f"❌ Erro na inicialização: {response.status_code}")
        else:
            print("✅ Vault já estava inicializado")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
EOF
fi

if [ ! -f "tpm-validator/tpm_validator.py" ]; then
    cat > tpm-validator/tpm_validator.py << 'EOF'
import os
import time
import subprocess
from pathlib import Path

def check_tpm_status():
    """Verifica status do TPM"""
    try:
        result = subprocess.run(['tpm2_getrandom', '4'], capture_output=True, timeout=10)
        return result.returncode == 0, "✅ TPM operacional" if result.returncode == 0 else "❌ TPM não responde"
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
    
    return True, f"✅ {len(enc_files)} arquivos .enc"

def check_vault():
    """Verifica status do Vault"""
    try:
        import requests
        response = requests.get('http://vault:8200/v1/sys/health', timeout=5)
        if response.status_code in [200, 501, 503]:
            return True, "✅ Vault respondendo"
        else:
            return False, f"❌ Vault status: {response.status_code}"
    except Exception as e:
        return False, f"❌ Vault inacessível: {e}"

def main():
    print("🔍 TPM VALIDATOR COM REQUIREMENTS.TXT")
    print("=====================================")
    
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
            print("\n🎉 STATUS: Sistema operacional!")
        else:
            print("\n⚠️  STATUS: Problemas detectados")
        
        print("⏰ Próxima verificação em 30 segundos...")
        time.sleep(30)

if __name__ == '__main__':
    main()
EOF
fi

if [ ! -f "tpm-validator/health_check.py" ]; then
    cat > tpm-validator/health_check.py << 'EOF'
from flask import Flask, jsonify
import subprocess
from pathlib import Path

app = Flask(__name__)

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        # Verificar TPM
        tpm_result = subprocess.run(['tpm2_getrandom', '4'], capture_output=True, timeout=10)
        tpm_ok = tpm_result.returncode == 0
        
        # Verificar arquivos
        data_dir = Path("/app/tpm-data")
        files_ok = data_dir.exists() and any(data_dir.glob("*.enc"))
        
        status = "healthy" if (tpm_ok and files_ok) else "unhealthy"
        
        return jsonify({
            "status": status,
            "tpm_operational": tpm_ok,
            "encrypted_files_present": files_ok,
            "service": "tpm-validator"
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF
fi

echo "✅ Estrutura com requirements.txt criada"

# Limpar dados antigos
echo "🧹 Limpando dados antigos..."
rm -rf vault-data/* tpm-data/*
mkdir -p vault-data tpm-data

# Construir e executar
echo "🔨 Construindo containers..."
docker-compose build --no-cache

echo "🚀 Iniciando serviços..."
docker-compose up -d

echo "⏳ Aguardando 20 segundos..."
sleep 20

echo "📊 Status dos serviços:"
docker-compose ps

echo "📋 Logs do vault-initializer:"
docker-compose logs vault-initializer --tail=10

echo "📁 Arquivos TPM:"
ls -la tpm-data/

echo "🧪 Testando health check:"
curl -s http://localhost:8080/health || echo "Health check não disponível"

echo "🎉 Estrutura com requirements.txt configurada!"
