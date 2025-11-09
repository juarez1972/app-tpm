#!/bin/bash

# Diretórios
CONFIG_DIR="./keylime-config"
DATA_DIR="./keylime-data"

# Criar diretórios
mkdir -p $CONFIG_DIR
mkdir -p $DATA_DIR

# Gerar certificados para Registrar
if [ ! -f "$DATA_DIR/reg_cert.pem" ]; then
    openssl req -new -x509 -days 365 -nodes -out $DATA_DIR/reg_cert.pem -keyout $DATA_DIR/reg_private_key.pem -subj "/CN=localhost"
    chmod 600 $DATA_DIR/reg_private_key.pem
fi

# Gerar certificados para Verifier
if [ ! -f "$DATA_DIR/verifier_cert.pem" ]; then
    openssl req -new -x509 -days 365 -nodes -out $DATA_DIR/verifier_cert.pem -keyout $DATA_DIR/verifier_private_key.pem -subj "/CN=localhost"
    chmod 600 $DATA_DIR/verifier_private_key.pem
fi

# Criar arquivo de configuração do Registrar
cat > $CONFIG_DIR/registrar.conf << EOF
[registrar]
database_url = sqlite:////var/lib/keylime/reg_data.sqlite

[webapp]
registrar_tls_cert = /var/lib/keylime/reg_cert.pem
registrar_private_key = /var/lib/keylime/reg_private_key.pem

[general]
re_encrypt_hmacs = False
EOF

# Criar arquivo de configuração do Verifier
cat > $CONFIG_DIR/verifier.conf << EOF
[verifier]
database_url = sqlite:////var/lib/keylime/verifier_data.sqlite

[webapp]
verifier_tls_cert = /var/lib/keylime/verifier_cert.pem
verifier_private_key = /var/lib/keylime/verifier_private_key.pem

[general]
re_encrypt_hmacs = False
EOF

echo "Configuração do Keylime concluída."
