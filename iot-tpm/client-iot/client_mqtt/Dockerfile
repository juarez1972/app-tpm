FROM python:3.11-slim

# Instala dependências para TPM e BCC
# Nota: linux-headers não é instalado aqui pois em python:3.11-slim os headers
# não correspondem ao kernel do host. Para BCC em produção, use Dockerfile.arm64
# com os headers corretos do dispositivo alvo.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libtss2-dev \
    tpm2-tools \
    bpfcc-tools \
    python3-bpfcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Executa o cliente MQTT
CMD ["python", "-u", "client_mqtt.py"]
