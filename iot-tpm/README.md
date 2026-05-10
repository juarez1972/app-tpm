# Projeto IoT Secure: Autenticação HOTP/TOTP com TPM e Vault

Este projeto implementa uma arquitetura robusta de cliente-servidor para dispositivos IoT, focada em segurança multicamada. A solução combina autenticação de dois fatores (2FA) via **OTP (One-Time Password)**, gestão centralizada de segredos no **HashiCorp Vault** e validação de integridade de hardware através de **TPM (Trusted Platform Module)**.

## 1. Arquitetura do Sistema

A solução está estruturada em dois componentes principais:

* **Servidor (API):** Desenvolvido em **FastAPI**, corre dentro de um contentor Docker. Gere o login inicial, valida tokens OTP e interage com o HashiCorp Vault para persistência e recuperação de segredos de configuração.
* **Cliente IoT:** Um script Python desenhado para correr em dispositivos periféricos. Antes de qualquer comunicação, valida se o hardware TPM está presente e funcional. Utiliza um segredo partilhado para gerar tokens dinâmicos que mantêm a sessão ativa.

## 2. Tecnologias Utilizadas

* **Linguagem:** Python 3.11+
* **API Framework:** FastAPI / Uvicorn
* **Segurança de Hardware:** `tpm2-tools` (Interface para o TPM 2.0)
* **Gestão de Segredos:** HashiCorp Vault (via biblioteca `hvac`)
* **Criptografia/OTP:** `pyotp` (RFC 4226/6238) e `cryptography`
* **Contentorização:** Docker e Docker Compose

## 3. Estrutura de Diretórios

```text
.
├── servidor/
│   ├── main.py            # Código fonte da API FastAPI
│   ├── Dockerfile         # Definição da imagem Docker do servidor
│   └── requirements.txt   # Dependências Python (FastAPI, hvac, etc.)
├── data/
│   └── logs/              # Logs de auditoria e acessos (Persistentes)
├── .env                   # Variáveis de ambiente e segredos
├── docker-compose.yml     # Orquestração do servidor e rede
└── cliente_iot.py         # Script para o dispositivo IoT (com validação TPM)

```

## 4. Configuração e Instalação

### Pré-requisitos

* Docker e Docker Compose instalados.
* HashiCorp Vault em execução no host (`localhost:8200`).
* Dispositivo cliente com suporte a TPM 2.0 e ferramentas `tpm2-tools` instaladas.

### Passo 1: Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto para armazenar as credenciais:

```env
# Configurações da App
APP_USER='cliente-otp'
APP_PASS='senha-aleatoria-123'
OTP_SECRET='semente_otp'

# Configurações do Vault Externo
VAULT_ADDR=http://host.docker.internal:8200
VAULT_TOKEN=root

```

### Passo 2: Iniciar o Servidor

```bash
docker-compose up --build -d

```

### Passo 3: Executar o Cliente

No dispositivo IoT ou simulador:

```bash
python cliente_iot.py

```

## 5. Fluxo de Segurança

1. **Verificação de Confiança (Hardware):** O cliente executa um teste de sanidade no TPM (`tpm2_getrandom`). Se falhar, a execução é abortada.
2. **Autenticação Primária:** O cliente autentica-se com credenciais fixas no endpoint `/login`.
3. **Segredo Partilhado:** O servidor utiliza o segredo definido (ou recuperado do Vault) para validar o próximo passo.
4. **Autenticação Contínua (OTP):** O cliente envia um código de 6 dígitos a cada 60 segundos. Se o código for inválido ou expirar, a sessão é encerrada no servidor.
5. **Auditoria:** Todos os eventos são registados na pasta `./data/logs/` para análise posterior.

## 6. Notas de Implementação

* **Comunicação Docker-Host:** O servidor utiliza `host.docker.internal` para comunicar com o Vault que corre fora do contentor.
* **Resiliência:** O uso de volumes Docker garante que os logs de segurança não sejam perdidos em caso de reinicialização do serviço.
* **Hardening:** O código do servidor não expõe o `OTP_SECRET` em logs, apenas o utiliza para validação em memória.

## 7. # Projeto IoT Secure: MQTT via TLS com TPM e Vault

Esta versão do projeto substitui a API REST por comunicação via protocolo **MQTT sobre TLS (MQTTS)**, garantindo menor latência e maior segurança em canais de comunicação persistentes.

## Alterações Principais
- **Protocolo:** Migração de HTTP/REST para MQTT (Porta 8883 padrão para TLS).
- **Segurança de Transporte:** Implementação obrigatória de certificados X.509 (CA, Server e Client).
- **Modelo:** Mudança para arquitetura Pub/Sub (Publicador/Subscritor).

## Estrutura
- `./servidor_mqtt/`: Subscriber que valida os tokens e consulta o Vault.
- `cliente_mqtt.py`: Publisher que valida o TPM e envia os códigos OTP.
- `./certs/`: Diretório onde devem ser depositados os certificados `.crt` e `.key`.

## Execução
1. Configure o seu Broker MQTT (ex: Mosquitto) para aceitar conexões TLS.
2. Atualize o arquivo `.env` com os caminhos dos certificados.
3. Inicie o servidor: `python servidor_mqtt/main.py`
4. Inicie o cliente: `python cliente_mqtt.py`

*Nota: O fluxo de validação TPM no cliente e a integração com Vault no servidor permanecem ativos.*

## Geração de certificados digitais
1. Como utilizar:

    Instale a dependência:
    Bash

    pip install cryptography

    Execute o script:
    Bash

    python gerar_certificados.py

    Distribuição dos arquivos:

        No Servidor MQTT (Broker): Você precisará do ca.crt, server.crt e server.key.

        No Cliente IoT: Você precisará apenas do ca.crt para que ele possa confiar no certificado apresentado pelo servidor.

2.  Observação sobre o SAN (Subject Alternative Name):

O script inclui host.docker.internal e localhost no certificado. Isso é vital para que o cliente não rejeite a conexão por "Hostname Mismatch". Se você for rodar em IPs específicos na sua rede, adicione-os na lista x509.SubjectAlternativeName dentro do script.
