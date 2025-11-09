#!/bin/bash

echo "🎯 INICIALIZADOR KEYLIME SERVER - CORRIGIDO"

# Limpeza agressiva
echo "🧹 Limpando TUDO..."
docker stop keylime-registrar keylime-verifier 2>/dev/null
docker rm keylime-registrar keylime-verifier 2>/dev/null
docker system prune -f

# Verificar imagem
echo "🔍 Testando imagem..."
if ! docker run --rm keylime_server_setup_keylime-registrar python3 -c "import keylime; print('✅ Keylime importa')" 2>/dev/null; then
    echo "❌ Imagem com problemas, rebuild..."
    docker-compose build --no-cache
fi

# Iniciar Registrar PRIMEIRO
echo "🔧 Iniciando Registrar (PRIMEIRO)..."
docker run -d \
  --name keylime-registrar \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-registrar \
  sh -c "python3 -c 'from keylime.cmd.registrar import main; main()'"

echo "⏳ Aguardando Registrar (20 segundos)..."
sleep 20

# Verificar Registrar
echo "=== REGISTRAR STATUS ==="
if docker ps | grep -q keylime-registrar; then
    echo "✅ Registrar RODANDO"
    echo "📝 Logs:"
    docker logs keylime-registrar --tail 5
else
    echo "❌ Registrar FALHOU"
    echo "🔍 Debug completo:"
    docker logs keylime-registrar
    echo "🔄 Tentando abordagem alternativa..."
    
    # Tentar com comando direto
    docker run -d \
      --name keylime-registrar \
      --network host \
      -v $(pwd)/keylime-data:/var/lib/keylime \
      -v $(pwd)/keylime-config:/etc/keylime \
      keylime_server_setup_keylime-registrar \
      python3 -m keylime.cmd.registrar
      
    sleep 15
fi

# Verificar novamente
if docker ps | grep -q keylime-registrar; then
    echo "🎉 Registrar FINALMENTE rodando!"
else
    echo "💥 Registrar não conseguiu iniciar"
    exit 1
fi

# Iniciar Verifier SEGUNDO
echo "🔧 Iniciando Verifier (SEGUNDO)..."
docker run -d \
  --name keylime-verifier \
  --network host \
  -v $(pwd)/keylime-data:/var/lib/keylime \
  -v $(pwd)/keylime-config:/etc/keylime \
  keylime_server_setup_keylime-verifier \
  sh -c "sleep 10 && python3 -c 'from keylime.cmd.verifier import main; main()'"

echo "⏳ Aguardando Verifier (25 segundos)..."
sleep 25

# Status final
echo ""
echo "=== 🎊 STATUS FINAL SERVER ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}" | grep -E "(registrar|verifier)"

if docker ps | grep -q keylime-registrar && docker ps | grep -q keylime-verifier; then
    echo ""
    echo "🎉🎉🎉 SERVIDOR KEYLIME OPERACIONAL! 🎉🎉🎉"
    echo "📍 Registrar: http://localhost:8891"
    echo "📍 Verifier: http://localhost:8882"
else
    echo ""
    echo "⚠️  Servidor incompleto:"
    echo "Registrar:" $(docker ps | grep keylime-registrar | wc -l)
    echo "Verifier:" $(docker ps | grep keylime-verifier | wc -l)
fi
