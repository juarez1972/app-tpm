FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y \
    tpm2-tools \
    python3-pip \
    && pip3 install pytpm requests

COPY vault_initializer.py .

CMD ["python", "vault_initializer.py"]
