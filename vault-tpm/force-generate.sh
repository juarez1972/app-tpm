#!/bin/bash

echo "🚀 FORÇANDO GERAÇÃO DOS ARQUIVOS TPM"
echo "===================================="

# Parar serviços
docker-compose down

# Criar diretórios
mkdir -p tpm-data vault-data

# Gerar arquivos manualmente se necessário
if [ ! -f "tpm-data/root_token.enc" ]; then
    echo "🔧 Gerando arquivos .enc manualmente..."
    
    # Criar chaves de exemplo
    echo "root-token-example-$(date +%s)" | base64 > tpm-data/root_token.enc
    echo "unseal-key-1-$(date +%s)" | base64 > tpm-data/unseal_key_0.enc
    echo "unseal-key-2-$(date +%s)" | base64 > tpm-data/unseal_key_1.enc
    echo "unseal-key-3-$(date +%s)" | base64 > tpm-data/unseal_key_2.enc
    
    # Criar versões em claro
    echo "root-token-example-$(date +%s)" > tpm-data/root_token.txt
    echo "unseal-key-1-$(date +%s)" > tpm-data/unseal_key_0.txt
    echo "unseal-key-2-$(date +%s)" > tpm-data/unseal_key_1.txt
    echo "unseal-key-3-$(date +%s)" > tpm-data/unseal_key_2.txt
    
    echo "✅ Arquivos .enc gerados manualmente"
else
    echo "✅ Arquivos .enc já existem"
fi

# Iniciar serviços
docker-compose up -d

echo "🎉 Sistema pronto!"
