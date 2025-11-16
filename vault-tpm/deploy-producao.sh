#!/bin/bash

echo "🚀 DEPLOY DO SISTEMA TPM + VAULT - MODO PRODUÇÃO"
echo "================================================"

# Verificar se o TPM está disponível
echo "🔍 Verificando TPM..."
if [ ! -c /dev/tpm0 ] && [ ! -c /dev/tpmrm0 ]; then
    echo "❌ TPM não encontrado. Verifique:"
    echo "   - drivers TPM instalados"
    echo "   - permissões do dispositivo"
    echo "   - hardware TPM habilitado"
    exit 1
fi

echo "✅ TPM detectado"

# Parar serviços existentes
echo "🛑 Parando serviços existentes..."
docker-compose down

# Limpar dados antigos (cuidado em produção real)
echo "🧹 Limpando dados antigos..."
rm -rf tpm-data/* vault-data/*

# Construir e executar
echo "🔨 Construindo containers..."
docker-compose build --no-cache

echo "🚀 Iniciando serviços..."
docker-compose up -d

# Aguardar inicialização
echo "⏳ Aguardando inicialização..."
sleep 15

# Verificar status
echo "📊 Verificando status..."
docker-compose ps

# Verificar logs do initializer
echo "📋 Logs do vault-initializer:"
docker-compose logs vault-initializer

# Verificar se arquivos foram gerados
echo "📁 Verificando arquivos TPM:"
ls -la tpm-data/

echo "🎉 Deploy concluído!"
