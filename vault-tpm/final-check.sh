#!/bin/bash

echo "🎯 VERIFICAÇÃO FINAL DO SISTEMA"
echo "==============================="

echo ""
echo "📊 SERVIÇOS:"
docker-compose ps

echo ""
echo "📁 ARQUIVOS TPM:"
ls -la tpm-data/

echo ""
echo "🔗 VAULT:"
curl -s http://localhost:8201/v1/sys/health | python3 -m json.tool

echo ""
echo "🏥 HEALTH CHECK:"
curl -s http://localhost:8080/health | python3 -m json.tool

echo ""
echo "🔍 LOGS TPM-VALIDATOR:"
docker-compose logs tpm-validator --tail=5

echo ""
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "🎉 SISTEMA 100% OPERACIONAL!"
    echo ""
    echo "📝 PRÓXIMOS PASSOS:"
    echo "1. Acesse a UI do Vault: http://localhost:8201"
    echo "2. Use o token: cat tpm-data/root_token.txt"
    echo "3. Monitor: docker-compose logs -f tpm-validator"
else
    echo "⚠️  Verifique os logs para detalhes: docker-compose logs tpm-validator"
fi
