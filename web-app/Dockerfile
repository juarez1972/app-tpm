# Estágio 1: Imagem base com Python
FROM python:3.10-slim-bullseye

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Atualiza os pacotes e instala tpm2-tools, que é uma dependência de tempo de execução
RUN apt-get update && \
    apt-get install -y --no-install-recommends tpm2-tools && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos da aplicação, incluindo o segredo lacrado
COPY app.py .
COPY sealed.ctx .

# Expõe a porta em que a aplicação Flask irá rodar
EXPOSE 5000

# Define o comando para iniciar a aplicação quando o contêiner for executado
CMD ["python", "app.py"]
