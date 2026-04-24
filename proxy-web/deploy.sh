#!/bin/bash
GREEN='\033[0;32m'
NC='\033[0m'

# Carrega variáveis do .env de forma segura
if [ -f .env ]; then
    set -a            # Ativa exportação automática
    source .env       # Lê o arquivo
    set +a            # Desativa exportação automática
else
    echo "Erro: Arquivo .env não encontrado!"
    exit 1
fi

echo -e "${GREEN}### Iniciando Deploy para ${EXTERNAL_DOMAIN} ###${NC}"

mkdir -p proxy/certs proxy/templates

# Gera certificado usando o domínio definido no .env
if [ ! -f proxy/certs/fullchain.pem ]; then
    echo "Gerando certificados para $EXTERNAL_DOMAIN..."
    openssl req -x509 -newkey rsa:4096 -keyout proxy/certs/privkey.pem \
    -out proxy/certs/fullchain.pem -days 365 -nodes \
    -subj "/C=BR/ST=DF/L=Brasilia/O=TI/CN=${EXTERNAL_DOMAIN}"
fi

# Sobe os containers
docker-compose down
docker-compose up --build -d

echo -e "${GREEN}### Sucesso! Acesse: https://${EXTERNAL_DOMAIN} ###${NC}"
