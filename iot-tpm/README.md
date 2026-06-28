# IoT-TPM: Agente de Autenticação Não-Interativa com TPM 2.0

> Componente do protótipo descrito em:
> **"A Hybrid Zero Trust Architecture for Non-Interactive Authentication"**
> Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. — PPGIa/PUCPR, Brazil.

Este diretório implementa o **agente nIA (non-Interactive Authentication)** para dispositivos IoT, realizando autenticação contínua ancorada em hardware TPM 2.0. Suporta dois protocolos de transporte: **REST/HTTPS** e **MQTT sobre TLS (MQTTS)**.

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Estrutura de Diretórios](#3-estrutura-de-diretórios)
4. [Pré-requisitos](#4-pré-requisitos)
5. [Configuração](#5-configuração)
6. [Execução](#6-execução)
   - 6.1 [Cliente REST + Servidor FastAPI](#61-cliente-rest--servidor-fastapi)
   - 6.2 [Cliente MQTT + Broker TLS](#62-cliente-mqtt--broker-tls)
   - 6.3 [Entrypoint do Contêiner: unseal_and_start.py](#63-entrypoint-do-contêiner-unseal_and_startpy)
7. [Fluxo de Segurança](#7-fluxo-de-segurança)
8. [Validação dos Componentes](#8-validação-dos-componentes)
9. [Geração de Certificados](#9-geração-de-certificados)
10. [Build Multi-Arquitetura (ARM64)](#10-build-multi-arquitetura-arm64)
11. [Notas de Implementação](#11-notas-de-implementação)

---

## 1. Visão Geral

O agente IoT-TPM implementa o **Layer 1** (Hardware Root of Trust) da arquitetura híbrida descrita no artigo de referência. Antes de qualquer comunicação, o dispositivo:

1. Verifica a integridade e presença do TPM 2.0 via `tpm2_getrandom`.
2. Usa o segredo provisionado no TPM NVRAM (atributos `fixedtpm` + `fixedparent`) para gerar tokens HOTP/TOTP sem expor a chave.
3. Autentica-se de forma contínua ao servidor, que valida os tokens com o segredo armazenado no **HashiCorp Vault**.

Se o TPM não estiver operacional, a autenticação é **abortada** — comportamento esperado pelo modelo de dois canais (Seção VI.D do artigo).

---

## 2. Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                      Dispositivo IoT                        │
│                                                             │
│  ┌───────────┐   tpm2_getrandom   ┌────────────────────┐   │
│  │  TPM 2.0  │ ◀─────────────────▶│   nIA Agent        │   │
│  │ (NVRAM)   │   HMAC(K, counter) │   cliente_iot.py   │   │
│  └───────────┘                    └────────┬───────────┘   │
└───────────────────────────────────────────┼───────────────┘
                                            │
                         REST/HTTPS  ou  MQTT sobre TLS
                                            │
┌───────────────────────────────────────────▼───────────────┐
│                         Servidor                           │
│                                                            │
│  ┌─────────────┐     ┌──────────────────────────────────┐  │
│  │  FastAPI    │     │       HashiCorp Vault             │  │
│  │  (REST API) │────▶│  Recupera OTP_SECRET via hvac    │  │
│  │  ou Broker  │     │  Valida token HOTP/TOTP           │  │
│  │  MQTT       │     └──────────────────────────────────┘  │
│  └─────────────┘                                           │
└────────────────────────────────────────────────────────────┘
```

**Protocolos suportados:**

| Protocolo | Porta padrão | Caso de uso |
|-----------|-------------|-------------|
| REST/HTTPS | 443 / 8000 | Integração com APIs, maior payload |
| MQTT sobre TLS | 8883 | IoT de baixa largura de banda, telemetria |

---

## 3. Estrutura de Diretórios

```text
iot-tpm/
├── Dockerfile                        # entrypoint Docker do contêiner cliente IoT + Twingate
├── unseal_and_start.py               # entrypoint real do contêiner (ver Seção 6.3)
├── sealed_key.pub                    # segredos selados pelo TPM (não exportáveis em plaintext)
├── sealed_key.priv                   # segredos selados pelo TPM (não exportáveis em plaintext)
├── client-iot/
│   ├── client_mqtt/
│   │   ├── client_mqtt.py
│   │   └── requirements.txt
│   └── client_rest_api/
│       ├── client_iot.py
│       └── requirements.txt
├── server/
│   ├── certs/                # ca.crt, server.crt, server.key (não versionados)
│   ├── gerar_certificados.py # gera os certs acima
│   ├── server_rest_api/
│   │   ├── main.py
│   │   ├── server_rest_api.py        # versão standalone para testes (sem Vault)
│   │   ├── docker-compose.yml
│   │   └── requirements.txt
│   └── server_mqtt/
│       ├── server_mqtt.py
│       └── requirements.txt
├── certs/                            # (planejado)
├── data/
│   └── logs/                         # (planejado)
├── .env                              # (planejado)
└── README.md
```

---

## 4. Pré-requisitos

### Hardware e Sistema

- Dispositivo com TPM 2.0 (ex.: Infineon SLB9670, Raspberry Pi 4/5) ou simulador [`swtpm`](https://github.com/stefanberger/swtpm) para ambientes de desenvolvimento.
- Docker e Docker Compose instalados no servidor.
- Python 3.11+ no dispositivo cliente.

### Servidor externo

- **HashiCorp Vault** em execução e acessível (`http://localhost:8200` por padrão).
- **Broker MQTT** configurado para TLS na porta 8883 (somente para o cliente MQTT).

### Ferramentas TPM no cliente

```bash
sudo apt update && sudo apt install tpm2-tools

# Validação funcional — deve retornar bytes aleatórios sem erro
sudo tpm2_getrandom 4
```

---

## 5. Configuração

Crie o arquivo `.env` na raiz de `iot-tpm/` com base no modelo abaixo. **Nunca versione este arquivo.**

> **Nota:** O arquivo `.env`, bem como `certs/`, `data/logs/` e `gerar_certificados.py`, são artefatos criados pelo usuário localmente e não estão versionados no repositório.

```env
# ── Credenciais da aplicação ────────────────────────────────────
APP_USER=cliente-otp
APP_PASS=senha-aleatoria-forte-aqui
OTP_SECRET=semente_otp_base32_aqui

# ── Vault ────────────────────────────────────────────────────────
VAULT_ADDR=http://host.docker.internal:8200
VAULT_TOKEN=root

# ── MQTT (somente para o cliente MQTT) ──────────────────────────
MQTT_BROKER=endereco_do_broker
MQTT_PORT=8883
MQTT_TOPIC_VERIFY=iot/verify
CA_CERT=/app/certs/ca.crt
CLIENT_CERT=/app/certs/client.crt
CLIENT_KEY=/app/certs/client.key
```

> **Segurança:** Em produção, substitua o token `root` do Vault por um token de serviço com política de mínimo privilégio e TTL curto.

---

## 6. Execução

### 6.1 Cliente REST + Servidor FastAPI

**Servidor:**

```bash
cd server/server_rest_api/

# Build e inicialização em background
docker compose up --build -d

# Verificar logs
docker compose logs -f
```

**Cliente IoT (no dispositivo):**

```bash
cd client-iot/client_rest_api/

pip install -r requirements.txt

# O script verifica o TPM antes de autenticar
python client_iot.py
```

**Fluxo REST:**

1. `POST /login` → credenciais fixas → recebe `session_token`.
2. A cada 60 s: `POST /verify` → `session_token` + código TOTP de 6 dígitos.
3. Código inválido ou expirado → sessão encerrada imediatamente no servidor.

---

### 6.2 Cliente MQTT + Broker TLS

**Pré-requisito:** gere os certificados (ver [Seção 9](#9-geração-de-certificados)) e configure o broker (ex.: Mosquitto) para TLS na porta 8883.

**Servidor MQTT (subscriber):**

```bash
cd server/server_mqtt/

pip install -r requirements.txt
python server/server_mqtt/server_mqtt.py
```

**Cliente IoT (publisher):**

```bash
cd client-iot/client_mqtt/

pip install -r requirements.txt
python client_mqtt.py
```

**Diferenças em relação ao REST:**

| Aspecto | REST | MQTT |
|---------|------|------|
| Protocolo | HTTP/HTTPS | MQTT sobre TLS (porta 8883) |
| Modelo | Request/Response | Pub/Sub |
| Latência | Maior | Menor |
| Ideal para | APIs, payloads maiores | Telemetria, dispositivos restritos |

---

### 6.3 Entrypoint do Contêiner: `unseal_and_start.py`

O `unseal_and_start.py` é o `ENTRYPOINT` real definido no `Dockerfile` do contêiner cliente IoT + Twingate. Ele executa o seguinte fluxo na inicialização:

1. **Detecta o TPM** em `/dev/tpmrm0`. Se o dispositivo não estiver acessível, a inicialização é abortada.
2. **Faz unseal da chave de serviço** via `tpm2_unseal`, gravando o resultado em tmpfs (`/run/secrets/service_key.json`) — nunca em disco persistente.
3. **Configura e inicia o cliente Twingate** (ZTNA) utilizando a chave deserrada para estabelecer a identidade do dispositivo na rede Zero Trust.
4. **Destrói a chave em plaintext da RAM** imediatamente após o setup do Twingate, minimizando a janela de exposição do segredo.

Esse fluxo garante que a chave de serviço só existe em plaintext pelo tempo estritamente necessário para autenticação, e nunca é persistida em armazenamento não-volátil fora do TPM.

---

## 7. Fluxo de Segurança

```
Dispositivo IoT                              Servidor
──────────────                               ────────
     │
     │  1. tpm2_getrandom → verifica TPM
     │     Se falhar → ABORTA
     │
     │  2. POST /login (credenciais fixas)
     │ ─────────────────────────────────────────────▶
     │                                   Autentica usuário
     │                                   Busca OTP_SECRET no Vault
     │ ◀─────────────────────────────────────────────
     │     session_token
     │
     │  3. Loop a cada 60 s:
     │     Gera TOTP com OTP_SECRET
     │     POST /verify (session_token + TOTP)
     │ ─────────────────────────────────────────────▶
     │                                   Valida TOTP
     │                                   Registra evento em ./data/logs/
     │ ◀─────────────────────────────────────────────
     │     OK / Sessão encerrada
```

**Garantias de segurança:**

- O `OTP_SECRET` nunca é exposto em logs — apenas usado em memória para validação.
- A chave HOTP no TPM possui atributos `fixedtpm` e `fixedparent`: nunca sai do chip.
- Logs de auditoria persistem em volume Docker mesmo após reinicialização do serviço.
- No modo MQTT, toda comunicação usa TLS mútuo (mTLS) com certificados X.509.

---

## 8. Validação dos Componentes

Após iniciar os contêineres, valide a integração dos componentes críticos:

### TPM 2.0

```bash
# Verificar acessibilidade do TPM no host
ls /dev/tpm* && sudo tpm2_getrandom 4

# Dentro do contêiner cliente
docker exec client-iot tpm2_getcap properties-fixed
```

### Vault

```bash
# Verificar status do Vault
curl -s http://localhost:8200/v1/sys/health | python3 -m json.tool

# Confirmar que o secret está acessível
vault kv get secret/iot-tpm
```

### MQTT (se aplicável)

```bash
# Testar conexão TLS com o broker
mosquitto_pub -h $MQTT_BROKER -p 8883 \
  --cafile certs/ca.crt \
  --certfile certs/client.crt \
  --keyfile certs/client.key \
  -t iot/test -m "ping" -d
```

---

## 9. Geração de Certificados

Para o modo MQTT com TLS, utilize o script incluído:

> **Nota:** O script `gerar_certificados.py`, bem como os diretórios `certs/` e `data/logs/`, são criados pelo usuário localmente e não estão versionados no repositório. Execute os passos abaixo no ambiente de desenvolvimento antes de iniciar os serviços.

cd iot-tpm/server/                   
```bash
# Instalar dependência
pip install cryptography

# Gerar CA, certificado de servidor e certificado de cliente
python gerar_certificados.py
```

**Distribuição dos arquivos gerados:**

| Arquivo | Servidor MQTT (Broker) | Cliente IoT |
|---------|----------------------|-------------|
| `ca.crt` | ✅ | ✅ |
| `server.crt` | ✅ | ❌ |
| `server.key` | ✅ | ❌ |
| `client.crt` | ❌ | ✅ (se mTLS) |
| `client.key` | ❌ | ✅ (se mTLS) |

> **SAN (Subject Alternative Name):** O script inclui `host.docker.internal` e `localhost` por padrão. Para implantações em IPs específicos da rede, adicione-os na lista `x509.SubjectAlternativeName` dentro de `gerar_certificados.py` antes de executar.

---

## 10. Build Multi-Arquitetura (ARM64)

O `docker-compose.yml` define dois serviços com profiles separados: `dev` (x86_64) e `arm64` (Raspberry Pi 4/5). O profile deve ser especificado explicitamente em todos os comandos — sem ele, o Compose ignora ambos os serviços e não realiza nenhum build.

### Em máquina virtual ou host x86_64 (emulação via QEMU)

Esse setup é necessário **uma única vez** por máquina host:

```bash
# 1. Registrar os interpretadores QEMU no kernel do host
#    Ensina ao Linux que executáveis ARM devem ser traduzidos pelo QEMU
docker run --privileged --rm tonistiigi/binfmt --install all

# 2. Criar um builder multi-arch
docker buildx create --use
```

Após o setup, use sempre o `--profile` para indicar o ambiente:

```bash
# Build e execução local (x86_64)
docker compose --profile dev up --build

# Build ARM64 com emulação QEMU (testa o binário ARM no host x86)
docker compose --profile arm64 up --build

# Build sem cache (garante integridade das dependências)
docker compose --profile arm64 build --no-cache
docker compose --profile arm64 up
```

### No Raspberry Pi real (sem emulação)

No dispositivo ARM64 nativo, o QEMU não é necessário. O mesmo `Dockerfile.arm64` roda diretamente:

```bash
docker compose --profile arm64 up --build
```

> **Nota:** Sem o `--profile`, o comando `docker compose build` retorna `No services to build` porque ambos os serviços estão protegidos por profile.

---


## 11. Notas de Implementação

- **Docker → Host:** O servidor utiliza `host.docker.internal` para se comunicar com o Vault que roda fora do contêiner. Em Linux, pode ser necessário adicionar `--add-host=host.docker.internal:host-gateway` no `docker-compose.yml`.
- **Modo dev do Vault:** O `VAULT_TOKEN=root` é adequado apenas para desenvolvimento. Em produção, use políticas de mínimo privilégio com TTL curto.
- **swtpm para CI/CD:** Em pipelines sem hardware TPM, use o simulador `swtpm` para testes automatizados. O comportamento é idêntico ao TPM físico para fins de validação de software.
- **Hardening:** O código do servidor nunca expõe o `OTP_SECRET` em logs — apenas o utiliza para validação em memória, conforme recomendado na Seção V do artigo.
- **unseal_and_start.py:** A chave de serviço deserrada fica em tmpfs (`/run/secrets/`) e é destruída da RAM imediatamente após o setup do Twingate, eliminando persistência em texto claro fora do TPM.

---

*Parte do projeto [app-tpm](https://github.com/juarez1972/app-tpm) — PPGIa/PUCPR, Brasil.*

