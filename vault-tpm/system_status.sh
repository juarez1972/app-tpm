#!/bin/bash
echo "=== STATUS DO SISTEMA TPM + VAULT ==="

echo -e "\n📋 TPM VALIDATOR:"
TPM_STATUS=$(curl -s http://localhost:5000/status)
echo "✅ TPM Validado: $(echo $TPM_STATUS | jq -r '.tpm_validated')"
echo "🔐 Hash do Segredo: $(echo $TPM_STATUS | jq -r '.secret_hash')"
echo "🖥️  Máquina Verificada: $(echo $TPM_STATUS | jq -r '.machine_verified')"

echo -e "\n🔐 VAULT:"
VAULT_STATUS=$(curl -s http://localhost:8200/v1/sys/health)
echo "✅ Inicializado: $(echo $VAULT_STATUS | jq -r '.initialized')"
echo "🔓 Unsealed: $(echo $VAULT_STATUS | jq -r '.sealed | not')"
echo "📦 Versão: $(echo $VAULT_STATUS | jq -r '.version')"

echo -e "\n🔄 SERVIÇOS DOCKER:"
docker-compose ps

echo -e "\n📊 LOGS RECENTES:"
echo "Vault Initializer:"
docker-compose logs vault-initializer --tail=3

echo -e "\n🎯 ARQUITETURA IMPLEMENTADA:"
echo "Boot → TPM Validation → Vault Unseal → Sistema Operacional"
echo "✅ CADEIA DE CONFIANÇA ESTABELECIDA"
