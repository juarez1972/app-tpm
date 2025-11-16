FROM ubuntu:22.04

# Definir variáveis de ambiente para evitar prompts interativos durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instalação de dependências: Curl, Python, TPM2-tools e pré-requisitos do Twingate
# 'iproute2' e 'iptables' são essenciais para a manipulação de rede do Twingate
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    tpm2-tools \
    libtss2-tcti-device0 \
    sudo \
    ca-certificates \
    gnupg \
    iproute2 \
    iptables \
    && rm -rf /var/lib/apt/lists/*

# Instalação do Cliente Twingate
# Utiliza-se o script oficial, mas em produção, recomenda-se fixar a versão ou
# configurar o repositório APT manualmente para controle de versão estrito [23]
RUN curl -s https://binaries.twingate.com/client/linux/install.sh | bash

# Criar diretório para a lógica Python e segredos selados
WORKDIR /app

# Copiar o script orquestrador Python
COPY unseal_and_start.py /app/

# Copiar os segredos SELADOS (partes pública e privada) para a imagem
# Estes arquivos são seguros para inclusão na imagem pois estão criptografados
COPY sealed_key.pub /app/
COPY sealed_key.priv /app/

# Definir o ponto de entrada
ENTRYPOINT ["python3", "/app/unseal_and_start.py"]
