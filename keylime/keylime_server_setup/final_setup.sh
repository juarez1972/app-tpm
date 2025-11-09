#!/bin/bash

echo "🎯 CONFIGURAÇÃO FINAL DO KEYLIME SERVER"

cd ~/app-tpm/keylime/keylime_server_setup

# Criar diretórios
mkdir -p keylime-config keylime-data

# Gerar certificados
echo "🔐 Gerando certificados..."
openssl req -new -x509 -days 365 -nodes \
  -out keylime-data/reg_cert.pem \
  -keyout keylime-data/reg_private_key.pem \
  -subj "/C=US/ST=State/L=City/O=Org/CN=localhost" 2>/dev/null

openssl req -new -x509 -days 365 -nodes \
  -out keylime-data/verifier_cert.pem \
  -keyout keylime-data/verifier_private_key.pem \
  -subj "/C=US/ST=State/L=City/O=Org/CN=localhost" 2>/dev/null

# Configurações com tls_dir
echo "📝 Criando configurações..."

# Registrar
cat > keylime-config/registrar.conf << 'EOF'
[registrar]
database_url = sqlite:////var/lib/keylime/reg_data.sqlite
tls_dir = /var/lib/keylime

[webapp]
registrar_tls_cert = /var/lib/keylime/reg_cert.pem
registrar_private_key = /var/lib/keylime/reg_private_key.pem
registrar_port = 8891

[general]
re_encrypt_hmacs = False
EOF

# Verifier
cat > keylime-config/verifier.conf << 'EOF'
[verifier]
database_url = sqlite:////var/lib/keylime/verifier_data.sqlite
registrar_ip = localhost
registrar_port = 8891
tls_dir = /var/lib/keylime

[webapp]
verifier_tls_cert = /var/lib/keylime/verifier_cert.pem
verifier_private_key = /var/lib/keylime/verifier_private_key.pem
verifier_port = 8882

[general]
re_encrypt_hmacs = False
EOF

# Logging básico
cat > keylime-config/logging.conf << 'EOF'
[loggers]
keys=root,keylime

[handlers]
keys=consoleHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=consoleHandler

[logger_keylime]
level=INFO
handlers=consoleHandler
qualname=keylime
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simpleFormatter
args=(sys.stdout,)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S
EOF

# Limpar containers
echo "🧹 Limpando containers..."
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null

# Iniciar serviços
echo "🚀 Iniciando serviços..."

# Registrar
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

sleep 30

if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar iniciado"
else
    echo "❌ Registrar falhou"
    docker logs keylime-registrar
    exit 1
fi

# Verifier
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  python3 -m keylime.cmd.verifier

sleep 25

echo ""
echo "=== 📊 STATUS FINAL ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

if docker ps | grep -q keylime-registrar && docker ps | grep -q keylime-verifier; then
    echo ""
    echo "🎉🎉🎉 KEYLIME SERVER OPERACIONAL! 🎉🎉🎉"
    echo ""
    echo "📍 Endpoints:"
    echo "   Registrar: https://localhost:8891"
    echo "   Verifier:  https://localhost:8882"
    echo ""
    echo "📋 Para verificar o funcionamento:"
    echo "   docker logs keylime-registrar -f"
    echo "   docker logs keylime-verifier -f"
else
    echo ""
    echo "⚠️  Serviços em execução:"
    echo "   Registrar: $(docker ps | grep keylime-registrar | wc -l)"
    echo "   Verifier:  $(docker ps | grep keylime-verifier | wc -l)"
fi
