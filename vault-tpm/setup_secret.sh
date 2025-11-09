#!/bin/bash

# setup_secret.sh - Versão extendida para suportar Vault

set -e

echo "=== Configuração do TPM e Vault ==="

# Diretórios de trabalho
TPM_DATA_DIR="./tpm-data"
VAULT_DATA_DIR="./vault-data"
VAULT_SCRIPTS_DIR="./scripts"
mkdir -p $TPM_DATA_DIR $VAULT_DATA_DIR $VAULT_SCRIPTS_DIR

# 1. Configuração do TPM (existente)
if [ ! -f "$TPM_DATA_DIR/secret" ]; then
    echo "Gerando segredo do TPM..."
    dd if=/dev/urandom of=$TPM_DATA_DIR/secret bs=32 count=1
    echo "Segredo gerado e armazenado em $TPM_DATA_DIR/secret"
else
    echo "Segredo do TPM já existe"
fi

# 2. Gerar chave de root token para o Vault baseada no TPM
if [ ! -f "$TPM_DATA_DIR/vault-root-key" ]; then
    echo "Gerando chave root do Vault baseada no TPM..."
    # Usar o segredo do TPM como base para a chave do Vault
    cat $TPM_DATA_DIR/secret | sha256sum | cut -d' ' -f1 > $TPM_DATA_DIR/vault-root-key
    echo "Chave root do Vault gerada"
fi

# 3. Configurar políticas do Vault
cat > $VAULT_SCRIPTS_DIR/setup_vault_policies.hcl << 'EOF'
# Política para o serviço de inicialização
path "sys/seal-status" {
  capabilities = ["read"]
}

path "sys/unseal" {
  capabilities = ["update"]
}

path "sys/health" {
  capabilities = ["read"]
}

path "sys/init" {
  capabilities = ["update"]
}

path "secret/data/tpm-verified/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
EOF

# 4. Configurar permissões
chmod 600 $TPM_DATA_DIR/secret
chmod 600 $TPM_DATA_DIR/vault-root-key

echo "=== Configuração concluída ==="
echo "Arquivos gerados:"
echo " - $TPM_DATA_DIR/secret (segredo TPM)"
echo " - $TPM_DATA_DIR/vault-root-key (chave root Vault)"
echo " - $VAULT_SCRIPTS_DIR/setup_vault_policies.hcl (políticas Vault)"
echo " "
echo "Para iniciar o sistema:"
echo "1. docker-compose up -d"
echo "2. Verifique os logs: docker-compose logs -f vault-initializer"
