#!/bin/bash
echo "=== RESOLVENDO CONFLITO DE PORTA 8200 ==="

echo "1. Parando serviços..."
docker-compose down

echo "2. Verificando processos na porta 8200..."
if lsof -i :8200 > /dev/null; then
    echo "Encontrei processos na porta 8200. Matando..."
    sudo lsof -ti:8200 | xargs sudo kill -9
    sleep 2
fi

echo "3. Removendo versão obsoleta do docker-compose.yml..."
# Criar backup
cp docker-compose.yml docker-compose.yml.backup
# Remover a linha version
grep -v '^version:' docker-compose.yml > docker-compose.yml.tmp && mv docker-compose.yml.tmp docker-compose.yml

echo "4. Reiniciando serviços..."
docker-compose up -d

echo "5. Verificando status..."
docker-compose ps
docker-compose logs vault --tail=10
