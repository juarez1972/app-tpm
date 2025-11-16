#!/bin/bash
# test_tpm_integration.sh - Testes específicos de integração TPM

COMPOSE_FILE="docker-compose.yml"

echo "=== Testes de Integração TPM ==="

# Test 1: Vault TPM seal/unseal
echo "1. Testando seal/unseal com TPM..."
docker-compose exec vault vault status

# Test 2: TPM key generation
echo "2. Testando geração de chaves TPM..."
docker-compose exec tpm-service tpm2_createprimary -c primary.ctx -Q
docker-compose exec tpm-service rm -f primary.ctx

# Test 3: Vault TPM auth
echo "3. Testando autenticação TPM..."
docker-compose exec vault vault auth list | grep tpm

# Test 4: TPM measurements
echo "4. Testando medições TPM..."
docker-compose exec tpm-service tpm2_pcrread

echo "=== Testes concluídos ==="
