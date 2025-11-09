#!/bin/bash

echo "🛡️  INICIALIZADOR KEYLIME COM FALLBACK GPG"

# Limpeza
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null

# Build
echo "📦 Build da imagem..."
docker-compose build --no-cache

# Teste
echo "🧪 Teste final..."
if docker run --rm keylime_server_setup_keylime-registrar python3 -c "import keylime; print('✅ Keylime base OK')"; then
    echo "✅ Teste passou"
else
    echo "❌ Teste falhou"
    exit 1
fi

# Registrar
echo "🔧 Iniciando Registrar..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

sleep 45

if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar OPERANTE"
else
    echo "❌ Registrar FALHOU - tentando abordagem alternativa..."
    # Tentar com ambiente Python limpo
    docker run -d \
      --name keylime-registrar \
      --network host \
      -v $(pwd)/keylime-data:/var/lib/keylime \
      -v $(pwd)/keylime-config:/etc/keylime \
      keylime_server_setup_keylime-registrar \
      sh -c "python3 -c 'import keylime.cmd.registrar; keylime.cmd.registrar.main()'"
    sleep 30
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

sleep 35

echo ""
echo "=== 📊 RESULTADO ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

if docker ps | grep -q keylime-registrar && docker ps | grep -q keylime-verifier; then
    echo ""
    echo "🎉🎉🎉 KEYLIME INSTALADO COM SUCESSO! 🎉🎉🎉"
    echo "📍 Registrar: porta 8891"
    echo "📍 Verifier: porta 8882" 
else
    echo ""
    echo "⚠️  Alguns serviços não iniciaram"
    echo "Registrar:" $(docker ps | grep keylime-registrar | wc -l)
    echo "Verifier:" $(docker ps | grep keylime-verifier | wc -l)
fi
