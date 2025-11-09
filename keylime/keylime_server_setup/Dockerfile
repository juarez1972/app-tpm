FROM registry.access.redhat.com/ubi8/ubi:latest

RUN dnf update -y -q && \
    dnf install -y -q python3-pip git python3-devel gcc openssl-devel openssl

RUN pip3 install --upgrade pip && \
    pip3 install cryptography && \
    pip3 install git+https://github.com/keylime/keylime.git

WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import keylime; print('Keylime OK')" || exit 1
