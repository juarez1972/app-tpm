#!/bin/bash

echo "🔍 TESTE MANUAL DO TPM"
echo "======================"

# Verificar dispositivos TPM
echo "📋 Dispositivos TPM:"
ls -la /dev/tpm* 2>/dev/null || echo "❌ Nenhum dispositivo TPM encontrado"

# Testar comandos básicos do TPM
echo ""
echo "🧪 Testando comandos TPM:"

# Testar tpm2_getrandom
echo "🔹 Testando tpm2_getrandom..."
tpm2_getrandom 4 --hex
if [ $? -eq 0 ]; then
    echo "✅ tpm2_getrandom funcionando"
else
    echo "❌ tpm2_getrandom falhou"
fi

# Testar tpm2_pcrread
echo "🔹 Testando tpm2_pcrread..."
tpm2_pcrread
if [ $? -eq 0 ]; then
    echo "✅ tpm2_pcrread funcionando"
else
    echo "❌ tpm2_pcrread falhou"
fi

# Testar diferentes TCTI
echo ""
echo "🔧 Testando diferentes TCTI:"

for tcti in "device:/dev/tpm0" "device:/dev/tpmrm0" "abrmd:bus_type=session"; do
    echo "🔹 Testando TCTI: $tcti"
    tpm2_getrandom 4 --tcti "$tcti" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✅ $tcti funcionando"
    else
        echo "   ❌ $tcti falhou"
    fi
done

echo ""
echo "🎯 RECOMENDAÇÕES:"
echo "• Verifique se o serviço tpm2-abrmd está rodando"
echo "• Verifique permissões do usuário no grupo 'tss'"
echo "• Execute: sudo usermod -a -G tss \$USER"
echo "• Reinicie o sistema ou faça logout/login"
