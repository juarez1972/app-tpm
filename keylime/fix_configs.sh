#!/bin/bash
echo "=== CORREÇÃO FINAL DA CONFIGURAÇÃO ==="

# Corrigir registrar.conf
cat > keylime_server_setup/keylime-config/registrar.conf << 'EOF'
[DEFAULT]
registrar_ip = 0.0.0.0
registrar_port = 8890
database_url = sqlite:////var/lib/keylime/registrar.sqlite
pool_size = 5,10

[registrar]
tls_dir = /var/lib/keylime
EOF

# Corrigir verifier.conf
cat > keylime_server_setup/keylime-config/verifier.conf << 'EOF'
[DEFAULT]
verifier_ip = 0.0.0.0
verifier_port = 8881
registrar_ip = localhost
registrar_port = 8890
database_url = sqlite:////var/lib/keylime/verifier.sqlite
pool_size = 5,10

[verifier]
tls_dir = /var/lib/keylime
EOF

echo "✅ Configurações corrigidas (formato pool_size = 5,10)"

# Reiniciar serviços
cd keylime_server_setup
sudo docker-compose restart

echo "Aguardando 15 segundos..."
sleep 15

# Verificar status
echo "=== STATUS DOS CONTAINERS ==="
sudo docker ps

echo "=== LOGS DO REGISTRAR ==="
sudo docker logs keylime-registrar --tail=15

# Testar se está funcionando
if curl -s http://localhost:8890/v1/status >/dev/null; then
    echo "🎉 ✅ REGISTRAR FUNCIONANDO!"
    echo "Porta 8890: ABERTA"
else
    echo "❌ Registrar ainda com problemas"
    echo "Verificando erro detalhado..."
    sudo docker logs keylime-registrar --tail=20
fi

# Verificar verifier também
if curl -s http://localhost:8881/v1/status >/dev/null; then
    echo "🎉 ✅ VERIFIER FUNCIONANDO!"
    echo "Porta 8881: ABERTA"
else
    echo "⚠️  Verifier pode estar inicializando..."
    sudo docker logs keylime-verifier --tail=10
fi
