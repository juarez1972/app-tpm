FROM fedora:38

# Instalar dependências do sistema
RUN dnf update -y -q && \
    dnf install -y -q python3-pip python3-devel git gcc openssl-devel openssl python3-gpg

# Copiar requirements.txt
COPY requirements.txt /tmp/requirements.txt

# Instalar dependências Python
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Instalar Keylime
RUN pip3 install git+https://github.com/keylime/keylime.git

WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import keylime; print('✅ Keylime OK')" || exit 1
