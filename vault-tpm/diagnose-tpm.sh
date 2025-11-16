#!/bin/bash

echo "🔍 DIAGNÓSTICO COMPLETO DO SISTEMA TPM"
echo "======================================"

echo ""
echo "📋 1. VERIFICANDO HOST:"
echo "----------------------"
echo "Dispositivos TPM no host:"
ls -la /dev/tpm* 2>/dev/null || echo "Nenhum dispositivo TPM encontrado"

echo ""
echo "Teste TPM no host:"
tpm2_getrandom 4 --tcti=device:/dev/tpmrm0 2>/dev/null && echo "✅ TPM /dev/tpmrm0 funciona" || echo "❌ TPM /dev/tpmrm0 falhou"
tpm2_getrandom 4 --tcti=device:/dev/tpm0 2>/dev/null && echo "✅ TPM /dev/tpm0 funciona" || echo "❌ TPM /dev/tpm0 falhou"

echo ""
echo "📋 2. VERIFICANDO CONTAINER:"
echo "---------------------------"
echo "Testando acesso ao TPM no container..."

docker-compose run --rm vault-initializer sh -c "
echo 'Dispositivos no container:'
ls -la /dev/tpm* 2>/dev/null || echo 'Nenhum dispositivo TPM encontrado'

echo ''
echo 'Testes TPM no container:'
tpm2_getrandom 4 --tcti=device:/dev/tpmrm0 2>/dev/null && echo '✅ TPM /dev/tpmrm0 funciona' || echo '❌ TPM /dev/tpmrm0 falhou'
tpm2_getrandom 4 --tcti=device:/dev/tpm0 2>/dev/null && echo '✅ TPM /dev/tpm0 funciona' || echo '❌ TPM /dev/tpm0 falhou'
tpm2_getrandom 4 2>/dev/null && echo '✅ TPM (default) funciona' || echo '❌ TPM (default) falhou'
"

echo ""
echo "📋 3. VERIFICANDO SERVIÇOS:"
echo "--------------------------"
docker-compose ps

echo ""
echo "📋 4. LOGS DO VAULT-INITIALIZER:"
echo "-------------------------------"
docker-compose logs vault-initializer --tail=50

echo ""
echo "📋 5. ARQUIVOS GERADOS:"
echo "----------------------"
ls -la tpm-data/ 2>/dev/null || echo "Diretório tpm-data não existe"

echo ""
echo "🎯 RECOMENDAÇÕES:"
if [ -f "tpm-data/root_token.enc" ]; then
    echo "✅ Arquivos .enc foram gerados"
    echo "💡 Sistema operacional (pode estar em modo fallback)"
else
    echo "❌ Arquivos .enc não foram gerados"
    echo "💡 Execute: docker-compose logs vault-initializer para detalhes"
fi
