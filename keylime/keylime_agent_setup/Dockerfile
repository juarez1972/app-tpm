FROM registry.access.redhat.com/ubi8/ubi:latest

# Instalar dependências do sistema
RUN dnf update -y -q && \
    dnf install -y -q python3-pip git python3-devel gcc openssl-devel openssl

# Instalar dependências Python
RUN pip3 install --upgrade pip && \
    pip3 install cryptography && \
    pip3 install git+https://github.com/keylime/keylime.git

WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import keylime; print('Keylime OK')" || exit 1
