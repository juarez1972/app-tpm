#!/bin/bash

echo "🔧 CORREÇÃO RÁPIDA - DOCKERFILES SIMPLIFICADOS"
echo "=============================================="

# Parar serviços
echo "🛑 Parando serviços..."
docker-compose down

# Limpar dados antigos (opcional)
echo "🧹 Limpando dados antigos..."
rm -rf tpm-data/* vault-data/*

# Reconstruir com Dockerfiles simplificados
echo "🔨 Reconstruindo containers..."
docker-compose build --no-cache

# Executar
echo "🚀 Iniciando serviços..."
docker-compose up -d

# Aguardar
echo "⏳ Aguardando inicialização..."
sleep 20

# Verificar logs
echo "📋 Logs do vault-initializer:"
docker-compose logs vault-initializer

# Verificar arquivos
echo "📁 Verificando arquivos TPM:"
ls -la tpm-data/ 2>/dev/null || echo "❌ Diretório vazio"

echo "🎉 Correção aplicada!"
