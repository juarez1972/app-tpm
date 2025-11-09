#!/bin/bash

echo "🔄 RECUPERAÇÃO E INICIALIZAÇÃO DO KEYLIME"

cd ~/app-tpm/keylime/keylime_server_setup

# Parar tudo
echo "🧹 Parando todos os serviços..."
docker stop keylime-registrar keylime-verifier keylime-agent vault-server 2>/dev/null
docker rm keylime-registrar keylime-verifier keylime-agent vault-server 2>/dev/null

# Corrigir certificados
echo "🔐 Corrigindo certificados..."
./fix_certificates.sh

# Configuração mínima garantida
echo "📝 Garantindo configurações..."
mkdir -p keylime-config

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

# Iniciar Registrar
echo "🚀 Iniciando Registrar..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

sleep 25

if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar iniciado com sucesso!"
else
    echo "❌ Registrar falhou - tentando abordagem alternativa..."
    # Tentar sem montar volumes para debug
    docker run -d \
      --name keylime-registrar \
      --network host \
      keylime_server_setup_keylime-registrar \
      python3 -c "
import os
print('Debug: Listando /var/lib/keylime...')
if os.path.exists('/var/lib/keylime'):
    for f in os.listdir('/var/lib/keylime'):
        print(f'  {f}')
else:
    print('  Diretório não existe')
print('Debug: Listando /etc/keylime...')
if os.path.exists('/etc/keylime'):
    for f in os.listdir('/etc/keylime'):
        print(f'  {f}')
else:
    print('  Diretório não existe')
"
    sleep 5
    docker logs keylime-registrar
    exit 1
fi

# Iniciar Verifier
echo "🚀 Iniciando Verifier..."
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  python3 -m keylime.cmd.verifier

sleep 20

# Reiniciar Agent e Vault
echo "🚀 Reiniciando Agent e Vault..."
cd ../keylime_agent_setup
docker-compose down 2>/dev/null
docker-compose up -d

echo ""
echo "=== 📊 STATUS FINAL ==="
cd ../keylime_server_setup
docker ps --format "table {{.Names}}\t{{.Status}}"

if docker ps | grep -q keylime-registrar; then
    echo ""
    echo "🎉 KEYLIME RECUPERADO E OPERACIONAL!"
else
    echo ""
    echo "⚠️  Registrar ainda não está rodando"
    echo "💡 Tente executar manualmente para debug:"
    echo "   docker run -it --rm --network host -v \$(pwd)/keylime-data:/var/lib/keylime -v \$(pwd)/keylime-config:/etc/keylime keylime_server_setup_keylime-registrar python3 -m keylime.cmd.registrar"
fi
