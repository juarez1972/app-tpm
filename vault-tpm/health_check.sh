#!/bin/sh
# Health check para verificar se o TPM está acessível

# Verificar se o dispositivo existe
if [ ! -c /dev/tpmrm0 ] && [ ! -c /dev/tpm0 ]; then
    echo "TPM device not found"
    exit 1
fi

# Tentar comando simples do TPM
if tpm2_getrandom 1 --tcti=device:/dev/tpmrm0 >/dev/null 2>&1; then
    exit 0
elif tpm2_getrandom 1 --tcti=device:/dev/tpm0 >/dev/null 2>&1; then
    exit 0
else
    echo "TPM not responding"
    exit 1
fi
