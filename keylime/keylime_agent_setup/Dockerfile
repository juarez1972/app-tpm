cd ../keylime_agent_setup

cat > Dockerfile << 'EOF'
FROM fedora:38

RUN dnf update -y -q && \
    dnf install -y -q python3-pip python3-devel git gcc openssl-devel openssl

COPY requirements.txt .

RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt && \
    pip3 install git+https://github.com/keylime/keylime.git

WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import keylime; print('Agent OK')" || exit 1
EOF

# Rebuild
docker-compose build --no-cache
