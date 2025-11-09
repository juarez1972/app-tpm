#!/bin/bash
set -e

echo "=== INICIANDO TODOS OS SERVIÇOS ==="

# Parar serviços existentes
echo "Parando serviços existentes..."
cd keylime_server_setup && docker-compose down 2>/dev/null || true
cd ../keylime_agent_setup && docker-compose down 2>/dev/null || true

# Configurar permissões do TPM
echo "Configurando permissões do TPM..."
sudo chmod 666 /dev/tpm0 /dev/tpmrm0 2>/dev/null || echo "Aviso: Não foi possível configurar TPM"

# Reconstruir serviços
echo "Reconstruindo serviços..."
cd ../keylime_server_setup
docker-compose build --no-cache

# Iniciar servidor Keylime
echo "Iniciando servidor Keylime..."
docker-compose up -d

# Aguardar registrar inicializar com verificações
echo "Aguardando Registrar..."
for i in {1..12}; do
    if curl -s http://localhost:8890/v1/status >/dev/null; then
        echo "✅ Registrar está respondendo na tentativa $i"
        break
    else
        echo "⏳ Tentativa $i/12: Aguardando registrar..."
        sleep 5
    fi
    
    if [ $i -eq 12 ]; then
        echo "❌ Registrar não está respondendo após 60 segundos"
        echo "=== LOGS DO REGISTRAR ==="
        docker-compose logs keylime-registrar
        exit 1
    fi
done

# Aguardar verifier
echo "Aguardando Verifier..."
sleep 15

# Iniciar agente
echo "Iniciando agente Keylime e Vault..."
cd ../keylime_agent_setup
docker-compose build --no-cache
docker-compose up -d

# Aguardar inicialização
sleep 25

echo "=== VERIFICAÇÃO FINAL ==="
echo "Containers rodando:"
docker ps

echo -e "\nPortas:"
for port in 8890 8881 9002 8200; do
    if nc -z localhost $port 2>/dev/null; then
        echo "✅ Porta $port: ABERTA"
    else
        echo "❌ Porta $port: FECHADA"
    fi
done

echo -e "\n=== STATUS DOS SERVIÇOS ==="
services=("keylime-registrar" "keylime-verifier" "vault-server" "keylime-agent")
for service in "${services[@]}"; do
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$service"; then
        echo "✅ $service: RODANDO"
    else
        echo "❌ $service: PARADO"
        docker logs "$service" --tail=5 2>/dev/null || echo "  Sem logs disponíveis"
    fi
done
