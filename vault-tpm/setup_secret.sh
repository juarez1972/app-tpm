#!/bin/bash

# setup_secret.sh - Configuração correta do TPM e Vault

set -e

echo "=== CONFIGURAÇÃO DO TPM E VAULT ==="

# Diretórios de trabalho
TPM_DATA_DIR="./tpm-data"
VAULT_DATA_DIR="./vault-data"
SCRIPTS_DIR="./scripts"
mkdir -p $TPM_DATA_DIR $VAULT_DATA_DIR $SCRIPTS_DIR

# 1. Configuração do TPM - Gerar segredo único
if [ ! -f "$TPM_DATA_DIR/secret" ]; then
    echo "Gerando segredo do TPM..."
    dd if=/dev/urandom of=$TPM_DATA_DIR/secret bs=32 count=1
    echo "Segredo TPM gerado e armazenado em $TPM_DATA_DIR/secret"
else
    echo "Segredo TPM já existe"
fi

# 2. Gerar token root para o Vault (sempre temp-root-token para modo desenvolvimento)
if [ ! -f "$TPM_DATA_DIR/vault-root-token" ]; then
    echo "Configurando token root do Vault..."
    echo "temp-root-token" > $TPM_DATA_DIR/vault-root-token
    echo "Token root do Vault configurado: temp-root-token"
else
    echo "Token root do Vault já existe"
fi

# 3. Configurar permissões
chmod 600 $TPM_DATA_DIR/secret
chmod 600 $TPM_DATA_DIR/vault-root-token

echo "=== CONFIGURAÇÃO CONCLUÍDA ==="
echo "Arquivos gerados em $TPM_DATA_DIR/:"
echo " - secret (segredo TPM - 32 bytes)"
echo " - vault-root-token (token do Vault)"
echo ""
echo "Para iniciar o sistema:"
echo "1. docker-compose up -d"
echo "2. Verifique os logs: docker-compose logs -f vault-initializer"
