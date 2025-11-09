FROM fedora:38

# Instalar dependências
RUN dnf update -y -q && \
    dnf install -y -q python3-pip python3-devel git gcc openssl-devel openssl

# Copiar requirements
COPY requirements.txt .

# Instalar dependências
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt && \
    pip3 install git+https://github.com/keylime/keylime.git

WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import keylime; print('Keylime OK')" || exit 1
