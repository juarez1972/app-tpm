#!/bin/bash
# payload/autorun.sh

# Garante que o script falhe se qualquer comando falhar
set -e

# Define a API do Vault usando o nome DNS da rede interna
VAULT_API="http://vault:8200/v1/sys/unseal" # [15]
KEYS_FILE="unseal_keys.json" # 

echo "Atestação bem-sucedida. Iniciando 'unseal' do Vault em $VAULT_API..."

# Lê o arquivo JSON, extrai cada chave, e a envia para a API do Vault
# Requer 'curl' e 'jq' (instalados em nosso Dockerfile customizado)
jq -r '.keys' $KEYS_FILE | while read key ; do
  echo "Enviando chave de unseal..."
  curl -s -X PUT --data "{\"key\": \"$key\"}" $VAULT_API
done

echo "Processo de 'unseal' do Vault concluído."

# MEDIDA DE SEGURANÇA CRÍTICA:
# Remove as chaves de 'unseal' do tmpfs após o uso.
rm $KEYS_FILE

echo "Payload de 'unseal' removido com segurança."
