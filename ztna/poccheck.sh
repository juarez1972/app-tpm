#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # Sem cor

echo "--- Iniciando Health Check da PoC Zero Trust ---"

# 1. Validar se a rede compartilhada existe
if docker network inspect ziti-shared-net >/dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} Rede ziti-shared-net encontrada."
else
    echo -e "${RED}[ERRO]${NC} Rede ziti-shared-net não encontrada. Execute: docker network create ziti-shared-net"
fi

# 2. Validar se os containers estão rodando
containers=("ziti-controller" "ziti-edge-router" "keycloak" "keycloak-db")
for c in "${containers[@]}"; do
    if [ "$(docker inspect -f '{{.State.Running}}' $c 2>/dev/null)" == "true" ]; then
        echo -e "${GREEN}[OK]${NC} Container $c está rodando."
    else
        echo -e "${RED}[ERRO]${NC} Container $c está parado ou não existe."
    fi
done

# 3. Testar comunicação interna (Ziti -> Keycloak)
echo "Testando comunicação interna Ziti -> Keycloak..."
if docker exec ziti-controller curl -s --connect-timeout 5 http://keycloak:8080 > /dev/null; then
    echo -e "${GREEN}[OK]${NC} Ziti Controller consegue acessar o Keycloak via rede interna."
else
    echo -e "${RED}[ERRO]${NC} Falha na comunicação interna entre Ziti e Keycloak."
fi

# 4. Validar portas no Host
echo "Validando portas expostas no host..."
declare -A ports=( ["1280"]="Ziti API" ["8444"]="Ziti Console" ["8080"]="Keycloak Web" )
for port in "${!ports[@]}"; do
    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} Porta $port (${ports[$port]}) está aberta no localhost."
    else
        echo -e "${RED}[ERRO]${NC} Porta $port (${ports[$port]}) não responde no localhost."
    fi
done

echo "--- Check Finalizado ---"
