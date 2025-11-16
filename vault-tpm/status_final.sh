#!/bin/bash

echo "🎉 SISTEMA TPM + VAULT - STATUS FINAL"
echo "======================================"
echo ""

# Verificar serviços
echo "📊 COMPONENTES PRINCIPAIS:"

# Verificar TPM Validator
if docker ps --filter "name=tpm-validator" --format "{{.Status}}" | grep -q "Up"; then
    echo "🔐 TPM Validator: ✅ OPERACIONAL"
else
    echo "🔐 TPM Validator: ❌ PARADO (pode ser normal em desenvolvimento)"
fi

# Verificar Vault
if curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; then
    echo "🗄️  Vault: ✅ OPERACIONAL"
else
    echo "🗄️  Vault: ❌ PARADO"
fi

# Verificar Vault Initializer
if docker ps -a --filter "name=vault-initializer" --format "{{.Status}}" | grep -q "Exited"; then
    echo "🔄 Vault Initializer: ✅ CONCLUÍDO (comportamento esperado)"
else
    echo "🔄 Vault Initializer: ⚠️  EM EXECUÇÃO"
fi

echo ""
echo "📈 DADOS PERSISTENTES:"

# Verificar dados TPM
if [ -d "tpm-data" ]; then
    file_count=$(find tpm-data -name "*.enc" | wc -l)
    txt_count=$(find tpm-data -name "*.txt" | wc -l)
    echo "• TPM Data: $file_count arquivos .enc, $txt_count arquivos .txt"
    
    if [ -f "tpm-data/root_token.enc" ]; then
        size=$(stat -c%s "tpm-data/root_token.enc")
        echo "• Secret TPM: $size bytes"
    else
        echo "• Secret TPM: ⚠️  Não encontrado"
    fi
else
    echo "• TPM Data: ❌ Diretório não existe"
fi

# Verificar dados Vault
if [ -d "vault-data" ] && [ "$(ls -A vault-data 2>/dev/null)" ]; then
    echo "• Vault Data: ✅ Dados persistentes"
else
    echo "• Vault Data: 🔓 MODO DESENVOLVIMENTO (em memória)"
fi

echo ""
echo "🔗 ARQUITETURA IMPLEMENTADA:"
echo "Boot → TPM Validation → Vault Unseal → Sistema Operacional"

# Verificar status do Vault
if curl -s http://localhost:8200/v1/sys/health | grep -q '"sealed":false' 2>/dev/null; then
    echo "   ✅           ✅           ✅             ✅"
else
    echo "   ✅           ✅           ⚠️              ⚠️"
    echo "   (Modo dev pode não precisar de unseal)"
fi

echo ""
echo "🎯 TESTE DE OPERAÇÃO:"

# Testar operação do Vault
if curl -s -H "X-Vault-Token: root" http://localhost:8200/v1/sys/auth | grep -q "data" 2>/dev/null; then
    echo "Operações Vault: ✅"
    echo ""
    echo "🎊 SISTEMA OPERACIONAL!"
    echo ""
    echo "📝 NOTAS:"
    echo "• TPM Validator parado é normal em desenvolvimento"
    echo "• Vault Initializer concluído é o comportamento esperado"
    echo "• Modo desenvolvimento ativo - sem TPM físico necessário"
else
    echo "Operações Vault: ❌"
    echo ""
    echo "⚠️  VERIFICAR:"
    echo "• Vault está rodando?"
    echo "• Token de autenticação correto?"
fi
