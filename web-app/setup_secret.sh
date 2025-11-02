#!/bin/bash
set -e

SECRET_DATA="MySecretPassword"
SEALED_OBJECT_CONTEXT="sealed.ctx"
PRIMARY_CONTEXT="primary.ctx"

# Limpa contextos antigos, se existirem
rm -f $SEALED_OBJECT_CONTEXT $PRIMARY_CONTEXT

echo "1. Criando um objeto primário no TPM..."
tpm2_createprimary -C o -g sha256 -G rsa -c $PRIMARY_CONTEXT

echo "2. Criando o objeto lacrado com o segredo..."
# O segredo é passado via stdin para o comando tpm2_create
# A flag "-L sha256:" foi removida para compatibilidade
echo -n "$SECRET_DATA" | tpm2_create -C $PRIMARY_CONTEXT -i- -u sealed.pub -r sealed.priv

echo "3. Carregando o objeto lacrado no TPM para obter seu contexto..."
tpm2_load -C $PRIMARY_CONTEXT -u sealed.pub -r sealed.priv -c $SEALED_OBJECT_CONTEXT

echo "Setup concluído. O segredo está lacrado em '$SEALED_OBJECT_CONTEXT'."
# Limpa arquivos intermediários não necessários para o deslacramento
rm -f sealed.pub sealed.priv primary.ctx
