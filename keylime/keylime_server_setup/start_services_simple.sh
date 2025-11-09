#!/bin/bash

echo "🚀 INICIALIZADOR KEYLIME - SIMPLES E PRÁTICO"

# Parar serviços existentes
echo "🛑 Limpando serviços anteriores..."
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null

# Verificar se a imagem existe
if ! docker images | grep -q keylime_server_setup; then
    echo "📦 Construindo imagem..."
    docker-compose build
fi

# Teste rápido
echo "🧪 Teste rápido do Keylime..."
docker run --rm keylime_server_setup_keylime-registrar python3 -c "import keylime; print('✅ Keylime OK')"

# Iniciar Registrar
echo "🔧 Iniciando Registrar..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  python3 -m keylime.cmd.registrar

echo "⏳ Aguardando 30 segundos..."
sleep 30

# Verificar Registrar
if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar RODANDO"
    echo "📝 Últimas linhas do log:"
    docker logs keylime-registrar --tail 3
else
    echo "❌ Registrar PAROU"
    echo "🔍 Log completo:"
    docker logs keylime-registrar
    exit 1
fi

# Iniciar Verifier
echo "🔧 Iniciando Verifier..."
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  python3 -m keylime.cmd.verifier

echo "⏳ Aguardando 20 segundos..."
sleep 20

# Status final
echo ""
echo "=== 🎉 RESULTADO FINAL ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "✅ Serviços Keylime inicializados!"
echo "📊 Registrar: porta 8891"
echo "📊 Verifier: porta 8882" 
echo "📊 Agent: porta 9002 (quando iniciado)"
