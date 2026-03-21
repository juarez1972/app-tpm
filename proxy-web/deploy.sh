#!/bin/bash
GREEN='\033[0;32m'
NC='\033[0m'

# Carrega variáveis do .env para o script usar no certificado
export $(grep -v '^#' .env | xargs)

echo -e "${GREEN}### Iniciando Deploy para ${EXTERNAL_DOMAIN} ###${NC}"

mkdir -p proxy/certs proxy/templates

# Gera certificado usando o domínio definido no .env
if [ ! -f proxy/certs/fullchain.pem ]; then
    echo "Gerando certificados para $EXTERNAL_DOMAIN..."
    openssl req -x509 -newkey rsa:4096 -keyout proxy/certs/privkey.pem \
    -out proxy/certs/fullchain.pem -days 365 -nodes \
    -subj "/C=BR/ST=DF/L=Brasilia/O=TI/CN=${EXTERNAL_DOMAIN}"
fi

docker-compose down
docker-compose up --build -d

echo -e "${GREEN}### Sucesso! Acesse: https://${EXTERNAL_DOMAIN} ###${NC}"
