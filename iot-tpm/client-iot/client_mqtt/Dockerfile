FROM python:3.11-slim

# Dependências de runtime do TPM (tpm2-tools é usado para recuperar o segredo
# selado via tpm2_load/tpm2_unseal). Sem BCC/build-essential — não são usados.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libtss2-dev \
    tpm2-tools \
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
