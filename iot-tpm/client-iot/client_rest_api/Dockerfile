FROM python:3.11-slim

# Dependências de runtime do TPM (tpm2-tools é usado para recuperar o segredo
# selado via tpm2_load/tpm2_unseal).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libtss2-dev \
    tpm2-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "client_iot.py"]
