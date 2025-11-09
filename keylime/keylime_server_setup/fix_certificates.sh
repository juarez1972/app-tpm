#!/bin/bash

echo "🔐 CORREÇÃO DEFINITIVA DOS CERTIFICADOS KEYLIME"

cd ~/app-tpm/keylime/keylime_server_setup

# Garantir que o diretório existe
mkdir -p keylime-data

# Remover certificados antigos (se existirem)
echo "🧹 Removendo certificados antigos..."
rm -f keylime-data/*.pem

# Gerar certificado do Registrar com configuração completa
echo "🔐 Gerando certificado do Registrar..."
openssl genrsa -out keylime-data/reg_private_key.pem 2048
openssl req -new -key keylime-data/reg_private_key.pem \
  -out keylime-data/reg_cert.csr \
  -subj "/C=US/ST=State/L=City/O=Keylime Org/CN=registrar.localhost"

cat > keylime-data/reg_cert.cnf << 'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = State
L = City
O = Keylime Org
CN = registrar.localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = registrar.localhost
IP.1 = 127.0.0.1
EOF

openssl x509 -req -days 365 \
  -in keylime-data/reg_cert.csr \
  -signkey keylime-data/reg_private_key.pem \
  -out keylime-data/reg_cert.pem \
  -extfile keylime-data/reg_cert.cnf \
  -extensions v3_req

# Gerar certificado do Verifier
echo "🔐 Gerando certificado do Verifier..."
openssl genrsa -out keylime-data/verifier_private_key.pem 2048
openssl req -new -key keylime-data/verifier_private_key.pem \
  -out keylime-data/verifier_cert.csr \
  -subj "/C=US/ST=State/L=City/O=Keylime Org/CN=verifier.localhost"

cat > keylime-data/verifier_cert.cnf << 'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = State
L = City
O = Keylime Org
CN = verifier.localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = verifier.localhost
IP.1 = 127.0.0.1
EOF

openssl x509 -req -days 365 \
  -in keylime-data/verifier_cert.csr \
  -signkey keylime-data/verifier_private_key.pem \
  -out keylime-data/verifier_cert.pem \
  -extfile keylime-data/verifier_cert.cnf \
  -extensions v3_req

# Limpar arquivos temporários
rm -f keylime-data/*.csr keylime-data/*.cnf

# Verificar certificados gerados
echo "📋 Verificando certificados gerados:"
ls -la keylime-data/*.pem

echo "🔍 Validando certificados:"
for cert in keylime-data/*.pem; do
    if [[ $cert == *"cert.pem" ]]; then
        echo "=== $cert ==="
        openssl x509 -in "$cert" -text -noout | grep -E "(Subject:|Not After:|Subject Alternative Name:)"
    fi
done

echo "✅ Certificados gerados e validados com sucesso!"
