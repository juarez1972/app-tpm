#!/bin/bash

echo "🎯 INICIALIZADOR KEYLIME - VERSÃO FINAL"

# Limpeza
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null

# Build se necessário
if ! docker images | grep -q keylime_server_setup; then
    echo "📦 Build da imagem..."
    docker-compose build --no-cache
fi

# Teste crítico
echo "🧪 Teste crítico..."
docker run --rm keylime_server_setup_keylime-registrar python3 -c "
try:
    import keylime
    from keylime import signing
    print('✅ Keylime crítico OK')
except Exception as e:
    print(f'❌ Falha crítica: {e}')
    exit(1)
"

# Registrar
echo "🔧 Iniciando Registrar..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

sleep 40

if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar OPERANTE"
else
    echo "❌ Registrar FALHOU"
    docker logs keylime-registrar
    exit 1
fi

# Verifier
echo "🔧 Iniciando Verifier..."
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  python3 -m keylime.cmd.verifier

sleep 30

echo ""
echo "=== 🎊 RESULTADO FINAL ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

if docker ps | grep -q keylime-verifier; then
    echo ""
    echo "🎉🎉🎉 KEYLIME INSTALADO E OPERACIONAL! 🎉🎉🎉"
    echo "📊 Registrar: http://localhost:8891"
    echo "📊 Verifier: http://localhost:8882"
else
    echo ""
    echo "⚠️  Verifier não está rodando"
    docker logs keylime-verifier --tail 10
fi
