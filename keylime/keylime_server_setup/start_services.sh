#!/bin/bash

echo "🚀 INICIALIZADOR KEYLIME - PYTHON MODERNO"

# Build das imagens (se necessário)
echo "📦 Verificando imagens..."
if ! docker images | grep -q keylime_server_setup; then
    echo "Construindo imagens..."
    docker-compose build
fi

# Parar serviços existentes
echo "🛑 Parando serviços existentes..."
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null

# Iniciar Registrar
echo "🔧 Iniciando Keylime Registrar..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

echo "⏳ Aguardando Registrar (30 segundos)..."
sleep 30

# Verificar Registrar
if docker logs keylime-registrar --tail 3 2>/dev/null | grep -q "Running"; then
    echo "✅ Registrar rodando!"
else
    echo "⚠️  Registrar pode ter problemas, verificando..."
    docker logs keylime-registrar --tail 10
fi

# Iniciar Verifier
echo "🔧 Iniciando Keylime Verifier..."
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  python3 -m keylime.cmd.verifier

echo "⏳ Aguardando Verifier (20 segundos)..."
sleep 20

# Status final
echo ""
echo "=== 🎉 STATUS FINAL ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== 📊 VERIFICAÇÃO DE PORTAS ==="
netstat -tulpn | grep -E ':(8881|8882|8891)' || echo "Portas ainda não ouvindo..."

echo ""
echo "=== 📝 LOGS RÁPIDOS ==="
echo "Registrar:"
docker logs keylime-registrar --tail 3 2>/dev/null || echo "Registrar não disponível"

echo ""
echo "Verifier:"
docker logs keylime-verifier --tail 3 2>/dev/null || echo "Verifier não disponível"
