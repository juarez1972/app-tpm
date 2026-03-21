FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Executa com Gunicorn gerenciando o SSL
CMD ["gunicorn", "--bind", "0.0.0.0:443", \
     "--keyfile", "certs/privkey.pem", \
     "--certfile", "certs/fullchain.pem", \
     "--workers", "4", \
     "--timeout", "120", \
     "--chdir", "/app", \
     "app:app"]
