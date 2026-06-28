# Hybrid Zero Trust Architecture for Non-Interactive Authentication

> **Artigo de Referência:** "A Hybrid Zero Trust Architecture for Non-Interactive Authentication: Integrating Hardware Trust Anchors with Software-Defined Secret Management in Infrastructure as Code"  
> Langaro, J. S.; Santin, A. O.; Viegas, E. K.; Veiga, F. M.; Oliveira, J. — PPGIa/PUCPR, Brazil.

Este repositório contém a implementação de referência da arquitetura híbrida proposta no artigo acima. O protótipo integra **ancoragem de confiança em hardware** (TPM 2.0, Intel SGX, Intel TDX) com **gestão dinâmica de segredos por software** (HashiCorp Vault) e **micro-segmentação de rede** (Zero Trust Network Access — ZTNA), eliminando o problema do "Secret Zero" em ambientes de Infraestrutura como Código (IaC) e IoT.

---

## Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Pilares de Segurança](#2-pilares-de-segurança)
3. [Estrutura do Repositório](#3-estrutura-do-repositório)
4. [Tecnologias Utilizadas](#4-tecnologias-utilizadas)
5. [Configuração e Instalação](#5-configuração-e-instalação)
   - 5.1 [Pré-requisitos gerais](#51-pré-requisitos-gerais)
   - 5.2 [Suporte ao TPM no host Linux](#52-suporte-ao-tpm-no-host-linux)
   - 5.3 [Suporte ao SGX no host Linux](#53-suporte-ao-sgx-no-host-linux)
   - 5.4 [Suporte ao TDX no host Linux](#54-suporte-ao-tdx-no-host-linux)
6. [Módulos do Protótipo](#6-módulos-do-protótipo)
   - 6.1 [HOTP/HMAC (hotp/)](#61-hotphmac-hotp)
   - 6.2 [Vault + TPM Auto-Unseal (vault-tpm/)](#62-vault--tpm-auto-unseal-vault-tpm)
   - 6.3 [Cliente IoT com TPM (iot-tpm/)](#63-cliente-iot-com-tpm-iot-tpm)
   - 6.4 [ZTNA com OpenZiti e Keycloak (ztna/)](#64-ztna-com-openziti-e-keycloak-ztna)
   - 6.5 [Proxy Web (proxy-web/)](#65-proxy-web-proxy-web)
   - 6.6 [Simulação Adversarial com LLM (pentest/)](#66-simulação-adversarial-com-llm-pentest)
7. [Arquitetura Lógica do Fluxo nIA](#7-arquitetura-lógica-do-fluxo-nia)
8. [Resultados Experimentais](#8-resultados-experimentais)
9. [Roadmap](#9-roadmap)
10. [Licença](#10-licença)
11. [Autores](#11-autores)

---

## 1. Visão Geral da Arquitetura

A arquitetura baseia-se na premissa de que segurança exclusivamente em software é insuficiente para ambientes de Autenticação Não-Interativa (nIA). Ao ancorar a chave mestra do HashiCorp Vault em um **TPM 2.0** e ao deslocar o cálculo HMAC para dentro do hardware, garante-se que as chaves criptográficas **nunca saiam do silício**, mesmo sob comprometimento total do sistema operacional (MITRE ATT&CK T1003).

A camada de rede implementa **ZTNA** via OpenZiti ou Twingate, de modo que as credenciais ofuscadas por HOTP não possam ser reutilizadas fora de seu contexto estrito, neutralizando movimento lateral (T1021).

**Overhead medido:** ~75 ms por transação nIA completa; **RTO do Vault** reduzido de ~3 minutos (unseal manual) para ~300 ms (auto-unseal via TPM).

---

## 2. Pilares de Segurança

### 🛡️ Proteção via Hardware (TPM 2.0 / SGX / TDX)

| Camada | Tecnologia | Proteção Oferecida |
|---|---|---|
| Servidores baseline | TPM 2.0 (dTPM/fTPM) | Boot integrity (PCRs), Vault auto-unseal, HOTP via tpm2-pytss |
| Servidores críticos | Intel SGX + Gramine | Isolamento em enclave; memória cifrada pelo CPU (MEE) |
| Nuvem confidencial | Intel TDX + vTPM | Trust Domain completo; hipevisor não acessa RAM da VM |
| IoT / Edge | TPM 2.0 (Infineon SLB9670 / swtpm) | HMAC seed não exportável; contador monotônico em NVRAM |

- **Root of Trust:** chaves geradas e armazenadas dentro do TPM com atributos `fixedtpm` e `fixedparent`.
- **Sealing:** a unseal key do Vault é selada contra PCRs (0, 7), garantindo acesso apenas se o firmware não foi adulterado.
- **Sequestro de seeds HOTP:** o segredo compartilhado é um *Restricted Keyed-Hash* no TPM NVRAM — rollback fisicamente impossível.

### 🔐 Gestão de Segredos (HashiCorp Vault)

- **Auto-unseal via PKCS#11 → TPM:** elimina intervenção humana no boot.
- **Credenciais dinâmicas (TTL curto):** Vault emite tokens de curta duração para banco de dados e APIs via políticas IaC.
- **Ciclo de vida:** `Gerada (plaintext no Vault)` → `Ofuscada (HOTP keystream em trânsito)` → `Descartada`.

### 🌐 Conectividade Zero Trust (ZTNA)

- **Rede invisível:** OpenZiti (SDK embutido, sem portas abertas) ou Twingate (gerenciado).
- **Validação contínua de postura:** o gateway ZTNA verifica identidade, saúde do dispositivo e localização antes de aceitar o HOTP.
- **Micro-segmentação:** invalida sessões ao mudar de contexto (IP, dispositivo), bloqueando pivoting.

### 🔑 Autenticação HOTP Ancorada em Hardware

O agente nIA utiliza `tpm2-pytss` para solicitar ao TPM o cálculo HMAC sem nunca expor a chave:

```python
# Cálculo de HOTP delegado ao hardware (Layer 2 do artigo, Seção V)
from tpm2_pytss import ESAPI

def generate_hardware_hotp(nv_index, key_handle):
    ctx = ESAPI()
    ctx.nv_increment(nv_index)          # incrementa contador monotônico no TPM
    counter_val = ctx.nv_read(nv_index)
    hmac_result = ctx.hmac(key_handle, counter_val)
    return truncate_to_hotp(hmac_result) # chave nunca sai do chip
```

```
HOTP(K, C) = Truncate(HMAC-SHA-1_TPM(K, C))
```

---

## 3. Estrutura do Repositório

```
app-tpm/
├── hotp/               # Protótipo HOTP/TOTP cliente-servidor (Layer 2)
│   ├── Client/         # Cliente Python com pyotp
│   ├── Server/         # Servidor FastAPI com verificação TOTP
│   └── antigos/        # Versões anteriores (histórico de desenvolvimento)
│
├── vault-tpm/          # Vault + auto-unseal via TPM (Layer 1 + 2)
│   ├── vault-init/         # Inicializador: criptografa unseal keys com TPM
│   ├── tpm-validator/      # Health check: TPM, arquivos .enc e Vault
│   ├── tpm-data/            # Unseal keys e root token selados (.enc)
│   ├── scripts/
│   │   └── setup_vault_policies.hcl  # Políticas de acesso do Vault
│   ├── docker-compose.yml
│   ├── system_status.sh
│   └── test_tpm_integration.sh
│
├── iot-tpm/            # Agente nIA para IoT com verificação de TPM (Layer 1)
│   ├── client-iot/
│   │   ├── client_rest_api/     # Cliente REST + pyotp + validação TPM
│   │   │   └── client_iot.py
│   │   └── client_mqtt/         # Cliente MQTT para IoT de baixa largura de banda
│   │       └── client_mqtt.py
│   ├── server/
│   │   ├─ certs/             # certificados TLS (não versionados)
│   │   ├─ gerar_certificados.py
│   │   ├── server_rest_api/     # Backend FastAPI + integração Vault
│   │   │   ├── main.py          # Versão com Vault
│   │   │   ├── server_rest_api.py  # Versão standalone (testes sem Vault)
│   │   │   └── docker-compose.yml
│   │   └── server_mqtt/         # Subscriber MQTT + validação Vault
│   │       └── server_mqtt.py
│   ├── Dockerfile               # Entrypoint do contêiner IoT (TPM + Twingate)
│   └── unseal_and_start.py      # Unseal TPM → inicializa cliente Twingate (ZTNA)
│
├── ztna/               # PoC ZTNA com OpenZiti + Keycloak (Layer 3)
│   ├── docker-compose.yml
│   ├── check_poc.sh
│   ├── backup/              # Variantes anteriores do compose
│   └── openziti/
│       └── docker-compose-openziti.yml
│
├── proxy-web/          # Proxy web de demonstração com dashboard
│
├── pentest/            # Simulação adversarial com LLM (Seção VI.A do artigo)
│   ├── pentest.py      # Orquestrador básico (Nmap + OpenVAS)
│   ├── pentestv2.py    # Versão com Google Gemini API
│   └── pentestv3.py    # Versão completa: Cyber-Llama local (Ollama)
│
└── web-app/            # Aplicação de demonstração integrada
```

---

## 4. Tecnologias Utilizadas

| Categoria | Componente | Versão / Referência |
|---|---|---|
| Hardware Root of Trust | TPM 2.0 (ISO/IEC 11889) | Infineon SLB9670/SLB9665 ou swtpm |
| Confidential Computing | Intel SGX (Gramine/LibOS) | DCAP driver |
| Confidential VM | Intel TDX + vTPM | Sapphire Rapids+ |
| TPM SW Stack | tpm2-tss, tpm2-tools, tpm2-pytss | TCG-compliant |
| Secret Management | HashiCorp Vault (auto-unseal PKCS#11) | OSS |
| ZTNA | OpenZiti (Apache 2.0), Twingate, NetBird | — |
| IdP / MFA | Keycloak + Entra ID (OIDC/SAML) | — |
| Autenticação nIA | HOTP (RFC 4226), HMAC (RFC 2104) | — |
| Infraestrutura | Docker, Docker Compose, Terraform | — |
| Linguagem | Python 3.10+, Shell Script | — |
| Adversarial Simulation | Llama 3.x via Ollama / Google Gemini | Seção VI.A |

---

## 5. Configuração e Instalação

### 5.1 Pré-requisitos gerais

- Sistema com suporte a TPM 2.0 (ou simulador `swtpm` para CI/CD).
- Docker e Docker Compose instalados.
- Python 3.10+ com suporte a ambientes virtuais.

```bash
# Clonar o repositório
git clone https://github.com/juarez1972/app-tpm.git
cd app-tpm

# Criar e ativar ambiente virtual Python
python -m venv .venv
source .venv/bin/activate

# Instalar dependências de um módulo específico (ex: hotp/Client)
pip install -r hotp/Client/requirements.txt

# Para desativar o ambiente virtual
deactivate
```

---

### 5.2 Suporte ao TPM no host Linux

#### Verificar presença do TPM

```bash
# Dispositivo TPM no sysfs
ls /sys/class/tpm/
# Esperado: tpm0 ou tpmrm0

# Dispositivos de caractere em /dev
ls /dev/tpm*
# Esperado: /dev/tpm0 e/ou /dev/tpmrm0

# Módulos do kernel TPM carregados
lsmod | grep tpm
# Esperado: tpm_tis, tpm_tis_core, tpm, tpm_crb, etc.
```

#### Instalar ferramentas TPM2

```bash
sudo apt update
sudo apt install tpm2-tools

# Validação funcional: deve retornar bytes aleatórios
sudo tpm2_getrandom 4

# Exibir capacidades e versão do TPM
sudo tpm2_getcap properties-fixed | head
```

#### Provisionar HOTP no TPM (Sequência do artigo, Seção VI.B)

```bash
# 1. Auto-teste e inicialização
tpm2_selftest --full
tpm2_startup --clear

# 2. Criar índice NV e contador monotônico
tpm2_nvdefine -C o -s 8 \
  -a "ownerread|ownerwrite|authread|authwrite|extend" \
  -p nvpass 0x1500016

# 3. Gerar chave HMAC restrita (nunca exportável)
tpm2_createprimary -C o -g sha256 -G hmac -c primary.ctx
tpm2_create -C primary.ctx -g sha256 -G hmac \
  -u hmac.pub -r hmac.priv \
  -a "restricted|sign|fixedtpm|fixedparent"

# 4. Selar unseal key do Vault contra PCRs (boot integrity)
tpm2_pcrread sha256:7
tpm2_createpolicy --policy-pcr -l sha256:0,7 -L policy.pcr
tpm2_create -C primary.ctx -i unseal.key \
  -L policy.pcr -r seal.priv -u seal.pub -c seal.ctx
```

> Os atributos `fixedtpm` e `fixedparent` garantem que a chave **nunca saia do chip**, mesmo sob comprometimento total do SO.

---

### 5.3 Suporte ao SGX no host Linux

O processo envolve três etapas: verificar suporte no hardware/BIOS, instalar driver/SDK/PSW e rodar amostras de teste.

#### 1. Pré-requisitos e verificação

```bash
# Verificar flags SGX na CPU
grep -m1 sgx /proc/cpuinfo
```

No BIOS/UEFI, habilite SGX (modo *Enabled* ou *Software Controlled*) e desative Secure Boot se o driver não for assinado. Instale os headers do kernel correspondentes:

```bash
sudo apt install linux-headers-$(uname -r) build-essential dkms
```

#### 2. Instalar o driver DCAP

```bash
# Opção 1: Baixar instalador binário da Intel
wget https://download.01.org/intel-sgx/latest/linux-latest/distro/ubuntu22.04-server/sgx_linux_x64_driver_<versao>.bin
chmod +x sgx_linux_x64_driver_<versao>.bin && sudo ./sgx_linux_x64_driver_<versao>.bin

# Opção 2: Compilar do fonte
git clone https://github.com/intel/linux-sgx-driver
cd linux-sgx-driver && make
sudo cp isgx.ko /lib/modules/$(uname -r)/kernel/drivers/intel/sgx/
sudo depmod && sudo modprobe isgx

# Verificar ativação
lsmod | grep sgx
ls /dev/sgx/enclave  # ou /dev/isgx conforme versão do driver
```

#### 3. Instalar SDK e PSW

```bash
# Dependências de compilação
sudo apt install ocaml automake autoconf cmake python3 \
  libssl-dev libcurl4-openssl-dev libprotobuf-dev

# Baixar e instalar o SDK da Intel
wget https://download.01.org/intel-sgx/latest/linux-latest/distro/ubuntu22.04-server/sgx_linux_x64_sdk_<versao>.bin
chmod +x sgx_linux_x64_sdk_<versao>.bin
sudo ./sgx_linux_x64_sdk_<versao>.bin --prefix /opt/intel
source /opt/intel/sgxsdk/environment

# Instalar PSW via repositório APT da Intel
echo "deb [arch=amd64] https://download.01.org/intel-sgx/sgx_repo/ubuntu $(lsb_release -sc) main" \
  | sudo tee /etc/apt/sources.list.d/intel-sgx.list
sudo apt update && sudo apt install libsgx-urts libsgx-launch libsgx-epid libsgx-quote-ex
```

#### 4. Testar com amostras do SDK

```bash
cd /opt/intel/sgxsdk/SampleCode/SampleEnclave
make SGX_MODE=HW    # ou SGX_MODE=SIM para ambientes sem hardware
./app
```

> Confirme que o serviço AESM está ativo: `systemctl status aesmd`

---

### 5.4 Suporte ao TDX no host Linux

Requer processadores Intel Xeon com TDX (Sapphire Rapids, Emerald Rapids, Xeon 6) e Ubuntu Server 24.04 LTS.

#### 1. Atualizar o sistema

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

#### 2. Habilitar TDX na BIOS/UEFI

Na seção *CPU / Processor / Socket Configuration*, ative:

| Opção | Valor |
|---|---|
| Memory Encryption (TME) | Enable |
| Total Memory Encryption Multi-Tenant (TME-MT) | Enable |
| TME-MT memory integrity | **Disable** |
| Trust Domain Extension (TDX) | Enable |
| TDX Secure Arbitration Mode Loader (SEAM Loader) | Enable |
| TME-MT/TDX key split | Valor não zero |
| SW Guard Extensions (SGX) | Enable |

#### 3. Habilitar TDX no kernel

```bash
sudo nano /etc/default/grub
# Adicione em GRUB_CMDLINE_LINUX_DEFAULT:
# nohibernate kvm_intel.tdx=1

sudo update-grub && sudo reboot

# Verificar após o reboot
cat /proc/cmdline           # deve conter: nohibernate kvm_intel.tdx=1
sudo dmesg | grep -i tdx    # deve mostrar: virt/tdx: module initialized
```

#### 4. Instalar o stack de virtualização TDX

```bash
sudo apt install qemu-system-x86 ovmf-inteltdx libvirt-daemon-system libvirt-clients
ls -l /usr/share/ovmf/OVMF.inteltdx.ms.fd  # deve existir com alguns MB
```

#### 5. Usar o atalho Canonical/TDX (recomendado)

```bash
git clone -b noble-24.04 https://github.com/canonical/tdx.git
cd tdx

# Configurar atestação (opcional)
# TDX_SETUP_ATTESTATION=1  no arquivo setup-tdx-config

sudo ./setup-tdx-host.sh
sudo reboot

# Criar imagem de guest TD
cd tdx/guest-tools/image
sudo ./create-td-image.sh -v 24.04
# Gera: tdx-guest-ubuntu-24.04-*.qcow2
# Troque a senha padrão (123456) antes de usar em produção.
```

#### 6. Iniciar uma Trust Domain (TD) via QEMU

```bash
qemu-system-x86_64 \
  -accel kvm -smp 32 -m 16G -cpu host \
  -object '{"qom-type":"tdx-guest","id":"tdx","quote-generation-socket":{"type":"vsock","cid":"2","port":"4050"}}' \
  -object memory-backend-ram,id=mem0,size=16G \
  -machine q35,kernel_irqchip=split,confidential-guest-support=tdx,memory-backend=mem0 \
  -bios /usr/share/ovmf/OVMF.inteltdx.ms.fd \
  -nographic -nodefaults -vga none \
  -drive file=tdx-guest-ubuntu-24.04-generic.qcow2,if=none,id=virtio-disk0 \
  -device virtio-blk-pci,drive=virtio-disk0 \
  -serial stdio
```

#### 7. Verificar TDX dentro do guest

```bash
sudo dmesg | grep -i tdx
# Esperado: "tdx: Guest detected"
ls -l /dev/tdx_guest   # deve existir como char device
```

---

## 6. Módulos do Protótipo

### 6.1 HOTP/HMAC (`hotp/`)

Implementação de referência do pipeline HOTP/TOTP cliente-servidor (Layer 2 do artigo).

```bash
cd hotp

# Iniciar o servidor (FastAPI, porta 5000)
python Server/server.py
# O endpoint GET /setup retorna o OTP_SECRET dinâmico para sincronização

# Em outro terminal, obter o secret e configurar o cliente
# Edite hotp/Client/client.py: OTP_SECRET = "<valor do /setup>"
python Client/client.py
```

> **Atenção de segurança:** Em produção, substitua `FIXED_USER`, `FIXED_PASS` e `OTP_SECRET` por variáveis de ambiente. O HOTP do artigo é delegado ao TPM; o servidor atual usa `pyotp` como baseline para testes sem hardware.

**Fluxo:**
1. Cliente faz `POST /login` com credenciais → recebe `session_token`
2. A cada 60 s: cliente gera TOTP e envia `POST /verify` com token + OTP
3. Se OTP inválido, sessão é encerrada imediatamente

### 6.2 Vault + TPM Auto-Unseal (`vault-tpm/`)

Implementa o **Hardware Auto-Unseal** descrito na Seção V do artigo.

```bash
cd vault-tpm

# Subir o ambiente completo (Vault + TPM Initializer + Validator)
docker-compose up -d

# Verificar status do sistema
./system_status.sh

# Testar integração TPM ↔ Vault
./test_tpm_integration.sh
```

**Componentes:**
- `vault-init/vault_initializer.py`: criptografa unseal keys com TPM real ou simulado; salva `.enc` para produção e `.txt` para depuração.
- `tpm-validator/tpm_validator.py`: health check periódico (TPM, arquivos `.enc`, Vault) exposto na porta 8080.
- `scripts/setup_vault_policies.hcl`: políticas de acesso mínimo para os serviços que interagem com o Vault.

> **Nota:** Em modo dev (`VAULT_DEV_ROOT_TOKEN_ID=root`), o token padrão é `root`. Em produção, remova o modo dev e use apenas auto-unseal por TPM.

### 6.3 Cliente IoT com TPM (`iot-tpm/`)

Agente nIA para dispositivos IoT (Raspberry Pi 4/5, ARM64 Yocto) conforme Seção VI.B do artigo.

```bash
cd iot-tpm/

# 1. Unseal da chave via TPM e inicialização do cliente Twingate (ZTNA)
#    Executado automaticamente pelo contêiner via ENTRYPOINT
docker build -t iot-tpm-client .
docker run --rm --privileged --device /dev/tpmrm0 iot-tpm-client

# 2. Subir servidor REST API (docker-compose está em server/server_rest_api/)
cd server/server_rest_api/
docker compose up --build -d

# 3. Executar cliente REST (requer TPM ativo no host)
cd ../../
pip install -r client-iot/client_rest_api/requirements.txt
python client-iot/client_rest_api/client_iot.py

# Alternativa MQTT (IoT de baixa largura de banda)
pip install -r client-iot/client_mqtt/requirements.txt
python client-iot/client_mqtt/client_mqtt.py

# Servidor MQTT (subscriber)
python server/server_mqtt/server_mqtt.py
```

> O cliente IoT verifica o TPM via `tpm2_getrandom` antes de autenticar. Se o TPM não estiver operacional, a autenticação é abortada — comportamento esperado pelo modelo de dois canais (Seção VI.D). O `unseal_and_start.py` é o entrypoint Docker que faz o unseal da chave de serviço via TPM e inicia o cliente Twingate antes de qualquer comunicação.

### 6.4 ZTNA com OpenZiti e Keycloak (`ztna/`)

PoC do Layer 3 (Network Enforcement) do artigo, validando substituição de VPN por ZTNA baseado em identidade.

```bash
cd ztna

# 1. Criar rede compartilhada
docker network create ziti-shared-net

# 2. Configurar .env (copie e ajuste)
cp .env.example .env   # crie se não existir
# Defina: ZITI_PWD, ZITI_CTRL_EDGE_ADVERTISED_ADDRESS, etc.

# 3. Subir camadas em ordem
docker-compose -f backup/docker-compose-keycloak.yml up -d    # IdP
docker-compose -f openziti/docker-compose-openziti.yml up -d  # ZTNA

# 4. Acessar console de gestão
# https://<ip>:8444  → ZAC (Ziti Admin Console)
# http://<ip>:8080   → Keycloak
```

**Auto-enrollment para escala:**
```bash
docker exec -it ziti-controller ziti edge create ext-jwt-signer "keycloak-ztna" \
  --claims-property "email" \
  --issuer "http://localhost:8080/realms/ziti-realm" \
  --jwks-endpoint "http://keycloak:8080/realms/ziti-realm/protocol/openid-connect/certs" \
  --external-id-claim "email" \
  --auto-enrollment-enabled
```

### 6.5 Proxy Web (`proxy-web/`)

Dashboard de demonstração que agrega status dos componentes da arquitetura.

```bash
cd proxy-web
docker-compose up -d
# Acesse: http://localhost:<porta configurada>
./deploy.sh   # para atualizar sem downtime
```

### 6.6 Simulação Adversarial com LLM (`pentest/`)

Pipeline autônomo de red-team descrito na Seção VI.A do artigo, usando Llama 3.x local (via Ollama) ou Google Gemini.

```bash
cd pentest
pip install openai gvm-tools python-dotenv requests

# Configurar variáveis de ambiente
cat > .env << 'EOF'
OPENVAS_IP=192.168.x.x
OPENVAS_USER=admin
OPENVAS_PASS=sua_senha_forte
# GEMINI_API_KEY=chave_opcional_para_modo_cloud
EOF
```

| Versão | Descrição | Modelo LLM |
|---|---|---|
| `pentest.py` | Básico: Nmap + OpenVAS | — |
| `pentestv2.py` | Com análise por IA em nuvem | Google Gemini 2.0 Flash |
| `pentestv3.py` | Completo on-premises (produção) | Cyber-Llama / Llama 3.x (Ollama) |

```bash
# Instalar Ollama e modelo
curl -fsSL https://ollama.com/install.sh | sh
ollama run llama3

# Executar simulação (pentestv3 — modo local)
python pentestv3.py
```

> **Aviso legal:** Este software destina-se exclusivamente à **auditoria de segurança autorizada** e **pesquisa acadêmica**. O uso contra alvos sem permissão explícita é ilegal. Os autores não se responsabilizam pelo uso indevido.

---

## 7. Arquitetura Lógica do Fluxo nIA

```
┌──────────────────────────────────────────────────────────────────┐
│                    INFRAESTRUTURA IaC / IoT                      │
│                                                                  │
│  ┌─────────────┐     ┌──────────────────────────────────────┐   │
│  │  TPM 2.0    │     │          HashiCorp Vault              │   │
│  │  (Layer 1)  │────▶│  Auto-Unseal via PKCS#11 ← TPM Key   │   │
│  │  SGX / TDX  │     │  Credenciais dinâmicas (TTL curto)    │   │
│  └─────────────┘     └──────────────┬───────────────────────┘   │
│                                     │                            │
│                          ┌──────────▼──────────┐                │
│                          │   nIA Agent          │                │
│                          │   (tpm2-pytss)       │                │
│                          │   HOTP = TPM_HMAC(K,C)│               │
│                          └──────────┬──────────┘                │
│                                     │ Payload Ofuscado           │
│  ┌──────────────────────────────────▼──────────────────────────┐│
│  │              ZTNA Gateway (OpenZiti / Twingate)              ││
│  │   Valida: identidade + postura + localização + HOTP         ││
│  └──────────────────────────────────┬───────────────────────────┘│
│                                     │ Túnel TLS + ZTNA           │
│                          ┌──────────▼──────────┐                │
│                          │   Hub Services       │                │
│                          │   (GLPI, MariaDB,    │                │
│                          │    Nginx, NAS)        │                │
│                          └─────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘

Ciclo da credencial:
  Gerada (plaintext no Vault) → Ofuscada (HOTP em trânsito) → Descartada
```

**Fluxo de boot e autenticação:**

1. **Boot:** TPM valida integridade do firmware via PCRs.
2. **Unseal:** Vault solicita unseal key ao TPM via PKCS#11 (~300 ms).
3. **Auth:** Agente nIA gera HOTP via TPM e autentica ao ZTNA Gateway.
4. **Verificação ZTNA:** postura do dispositivo + HOTP validados simultaneamente.
5. **Transaction:** credencial trafega ofuscada por TLS + túnel ZTNA; apenas o Hub Services a desofusca.

---

## 8. Resultados Experimentais

Conforme a avaliação completa na Seção VI do artigo:

### Performance (1.000 requisições nIA concorrentes — Ubuntu 22.04 LTS)

| Operação | Software-only | TPM (Tier 1) | SGX (Tier 2) | TDX (Tier 3) |
|---|---|---|---|---|
| Geração HOTP | ~2 ms | ~65 ms | ~85 ms | ~70 ms |
| Autenticação Vault | ~45 ms | ~110 ms | ~130 ms | ~115 ms |
| nIA End-to-End | ~120 ms | ~195 ms | ~225 ms | ~205 ms |
| Auto-Unseal (RTO) | ~3 min | ~300 ms | ~350 ms | ~320 ms |

### Segurança (LLM Red-Team — 500 cenários MITRE ATT&CK)

| Tática MITRE | Técnica | Software-only | Arquitetura Híbrida |
|---|---|---|---|
| TA0001 | T1078 Valid Accounts | 8% | **0%** |
| TA0004 | T1068 Privilege Escalation | 15% | **0%** |
| TA0006 | T1003 OS Credential Dumping | 22% | **0%** |
| TA0006 | T1552 Unsecured Credentials | 35% | **0%** |
| TA0008 | T1021 Remote Services | 12% | **0%** |

> Taxa média de bypass na arquitetura de software puro: **18,4%**. Na arquitetura híbrida: **0%** em 500 cenários.

---

## 9. Roadmap

- [ ] **Post-Quantum TPM:** Avaliar CRYSTALS-Dilithium e SPHINCS+ em NV indices do TPM 2.0 para IoT de longo prazo.
- [ ] **LLM Red-Team Federado:** Distribuir a simulação adversarial entre múltiplos modelos locais para detecção por consenso.
- [ ] **Atestação TDX Cross-Cloud:** Padronizar atestação via vTPM entre AWS NitroTPM, Azure vTPM e GCP vTPM.
- [ ] **Integração Terraform completa:** Módulo IaC com labels `standard | high | critical` para seleção automática de tier de proteção.

---

## 10. Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).

---

## 11. Autores

Desenvolvido pelos pesquisadores do Programa de Pós-Graduação em Informática (PPGIa) — PUCPR, Brasil.

| # | Nome | E-mail |
|---|---|---|
| 1 | Juarez de Oliveira, M.Sc. | juarez.oliveira@pucpr.edu.br |
| 2 | Juliano Sartori Langaro, M.Sc. | juliano.langaro@pucpr.edu.br |
| 3 | Fellipe Medeiros Veiga, M.Sc. | fellipe.veiga@pucpr.edu.br |
| 4 | Altair Olivo Santin, PhD. *(Orientador)* | altair.santin@pucpr.br |

Financiado parcialmente pelo CNPq — bolsas nº 307706/2025-7 e 407879/2023-4.

