FROM python:3.9-alpine

WORKDIR /app

# Instalar dependências TPM no Alpine
RUN apk add --no-cache \
    tpm2-tools \
    tpm2-tss \
    tpm2-tss-engine

# Instalar Python packages
RUN pip install --upgrade pip
RUN pip install requests==2.31.0

COPY tpm_validator.py .

CMD ["python", "tpm_validator.py"]
