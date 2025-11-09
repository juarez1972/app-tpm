FROM python:3.9-slim-bullseye

WORKDIR /app

# Instalar dependências do TPM (Debian Bullseye tem esses pacotes)
RUN apt-get update && apt-get install -y \
    tpm2-tools \
    tpm2-tss \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY app.py .

# Criar usuário não-root
RUN useradd -m -u 1000 tpmuser && chown -R tpmuser:tpmuser /app
USER tpmuser

CMD ["python", "app.py"]
