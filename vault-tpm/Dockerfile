FROM python:3.9-slim-bullseye

WORKDIR /app

# Instalar apenas dependências básicas necessárias
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY app.py .

CMD ["python", "app.py"]
