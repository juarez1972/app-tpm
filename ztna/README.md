# ZTNA — Twingate Connector (Camada 3 / Network Enforcement)

Este módulo implementa a **Camada 3 (imposição de rede / ZTNA)** da arquitetura
Zero Trust híbrida do projeto `app-tpm`, usando o **Twingate** no modo
**Connector on-premises via Docker**. O objetivo é publicar os recursos internos
(o **Vault** do projeto `vault-tpm` e o **servidor IoT** do projeto `iot-tpm`)
sem expor nenhuma porta de entrada, aplicando acesso por identidade em vez de VPN.

> Este diretório substitui a antiga PoC baseada em OpenZiti + Keycloak. O modelo
> de ameaça e o papel na arquitetura continuam os mesmos (neutralizar movimento
> lateral, T1021); apenas a tecnologia de ZTNA passou a ser o Twingate.

---

## 1. Por que Twingate (Connector on-premises)

- **Sem portas de entrada:** o Connector faz apenas conexões de saída para o
  Relay do Twingate. Nenhuma porta precisa ser aberta no firewall do PPGIA96.
- **Acesso por identidade:** usuários/dispositivos autenticam no Twingate; o
  Connector só encaminha tráfego para Resources autorizados por política.
- **Complementa o HOTP/TOTP + TPM:** mesmo que uma credencial TOTP vaze, ela não
  pode ser usada fora do contexto de rede imposto pelo ZTNA.

---

## 2. Topologia dos dois servidores virtuais

```
                         Twingate Cloud (Controller + Relays)
                                       ▲  (somente saída)
                                       │
┌──────────────────────────────────────────────────────────┐
│  PPGIA96  (produção)                                       │
│                                                            │
│   ┌────────────────┐   ┌───────────────┐   ┌───────────┐  │
│   │ Vault          │   │ Servidor IoT  │   │ Twingate  │  │
│   │ (vault-tpm)    │◄──┤ (iot-tpm)     │   │ Connector │  │
│   │ :8200          │   │ REST :5000 /  │   │ (docker)  │  │
│   │ sementes TOTP  │   │ MQTT :8883    │   │  ztna/    │  │
│   └────────────────┘   └───────────────┘   └───────────┘  │
│         ▲ lê semente por device_id              │         │
│         └─────────────────────────────────────► publica   │
│                                                 Resources  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  PPGIA95  (testes / validação)                             │
│                                                            │
│   ┌──────────────────────┐   ┌──────────────────────────┐ │
│   │ Testes de segurança  │   │ Cliente/servidor IoT      │ │
│   │ (pentest/)           │   │ para validação (iot-tpm)  │ │
│   └──────────────────────┘   └──────────────────────────┘ │
│   Acessa os recursos do PPGIA96 através do Twingate.       │
└──────────────────────────────────────────────────────────┘
```

| Servidor | Papel | Componentes |
|---|---|---|
| **PPGIA96** | Produção | Vault (`vault-tpm`, `:8200`), servidor IoT (`iot-tpm`, REST `:5000` / MQTT `:8883`), **Twingate Connector** (este diretório) |
| **PPGIA95** | Testes / validação | Testes de segurança (`pentest/`) e cliente/servidor IoT para validação (`iot-tpm`), acessando os recursos do PPGIA96 via Twingate |

---

## 3. Deploy do Connector (PPGIA96)

### 3.1 Gerar os tokens no Admin Console

1. Acesse `https://<seu-networkname>.twingate.com` como administrador.
2. **Network → Connectors → Deploy Connector**.
3. Escolha **On-premises → Docker**. O Console gera um par de tokens
   (`ACCESS_TOKEN` e `REFRESH_TOKEN`) exibido **uma única vez**.

### 3.2 Subir o Connector

```bash
cd app-tpm/ztna/
cp .env.example .env
#  edite .env: TWINGATE_NETWORK, TWINGATE_ACCESS_TOKEN, TWINGATE_REFRESH_TOKEN
docker compose up -d
```

Verifique o status:

```bash
docker compose logs -f twingate-connector      # deve mostrar "Connected"
docker exec twingate-connector-ppgia96 ./connectord --version
```

No Admin Console, o Connector aparece como **Online**.

> O arquivo `.env` contém segredos e **não é versionado** (veja o `.gitignore`
> da raiz). Apenas o `.env.example` fica no repositório.

### 3.3 Detalhes do compose

- **Imagem:** `twingate/connector:1` (canal estável, atualizações automáticas de
  patch).
- **`sysctl net.ipv4.ping_group_range=0 2147483647`:** permite ao Connector
  medir latência (ICMP) até os Resources internos.
- **`restart: unless-stopped` + `pull_policy: always`:** reinício resiliente e
  imagem sempre atualizada ao recriar o container.
- **Label do Watchtower:** habilita atualização automática caso um Watchtower
  esteja em uso no host.

---

## 4. Publicar os Resources internos

No Admin Console (**Resources → Add Resource**), aponte para os serviços do
PPGIA96 usando o Connector deste diretório. Sugestão de Resources:

| Resource | Endereço interno (a partir do Connector) | Uso |
|---|---|---|
| Vault (vault-tpm) | `http://127.0.0.1:8200` ou IP interno do PPGIA96 | Escrita/leitura das sementes TOTP por `device_id` |
| Servidor IoT REST | `http://127.0.0.1:5000` | `POST /login`, `POST /verify` |
| Servidor IoT MQTT | `mqtt://127.0.0.1:8883` | Publicação/verificação de TOTP |

Em seguida, crie um **Group** e uma **Policy** liberando esses Resources apenas
para os usuários/dispositivos autorizados (por exemplo, o PPGIA95 e as estações
de administração). Nenhum outro tráfego alcança o PPGIA96.

### 4.1 Exemplo: Resource do servidor IoT + Policy liberando o PPGIA95

O objetivo é: **somente o PPGIA95** (e administradores) pode alcançar o servidor
IoT do PPGIA96; qualquer outra origem é bloqueada.

#### Pela UI do Admin Console

1. **Group** — crie o grupo `ppgia95-validacao` e associe a ele o usuário/serviço
   que roda o cliente IoT no PPGIA95 (**Team → Groups → Add Group**).
2. **Resource** — **Resources → Add Resource**:
   - **Address:** `10.0.0.96` (IP interno do PPGIA96) ou um alias interno, ex.
     `iot.ppgia96.local`.
   - **Connector:** o Connector deste diretório (`twingate-connector-ppgia96`).
   - **Restrict ports (recomendado):** `TCP 5000` (REST) e/ou `TCP 8883` (MQTT).
     Assim, mesmo autorizado, o PPGIA95 só alcança as portas do serviço IoT — o
     Vault (`:8200`) fica em um Resource separado, liberado apenas para admins.
3. **Policy / Access** — na aba **Access** do Resource, adicione o grupo
   `ppgia95-validacao`. Defina a **Security Policy** exigindo MFA e, se desejar,
   verificação de postura do dispositivo. Sem pertencer a esse grupo, nenhum
   host enxerga o Resource.

#### Declarativo via Terraform (coerente com a abordagem IaC do projeto)

```hcl
terraform {
  required_providers {
    twingate = {
      source  = "Twingate/twingate"
      version = "~> 3.0"
    }
  }
}

provider "twingate" {
  network    = "seu-networkname"          # TWINGATE_NETWORK
  api_token  = var.twingate_api_token     # token de API do Admin Console
}

# Connector on-premises que roda no PPGIA96 (este diretório).
data "twingate_remote_network" "ppgia96" {
  name = "ppgia96"
}

# Grupo que representa o servidor de validação PPGIA95.
resource "twingate_group" "ppgia95_validacao" {
  name = "ppgia95-validacao"
}

# Resource: servidor IoT do PPGIA96, restrito às portas REST/MQTT.
resource "twingate_resource" "iot_ppgia96" {
  name              = "IoT Server (PPGIA96)"
  address           = "10.0.0.96"                       # IP interno do PPGIA96
  remote_network_id = data.twingate_remote_network.ppgia96.id

  protocols = {
    allow_icmp = true
    tcp = {
      policy = "RESTRICTED"
      ports  = ["5000", "8883"]                          # REST e MQTT
    }
    udp = { policy = "DENY_ALL" }
  }

  # Policy de acesso: somente o grupo do PPGIA95, com MFA obrigatório.
  access_group {
    group_id           = twingate_group.ppgia95_validacao.id
    security_policy_id = data.twingate_security_policy.mfa.id

    # Reautorização periódica (relogin) do acesso do PPGIA95.
    access_policy {
      mode     = "AUTO_LOCK"
      duration = "7d"
    }
  }
}

# Security Policy pré-definida no Admin Console que exige MFA.
data "twingate_security_policy" "mfa" {
  name = "Require MFA"
}
```

> **Princípio do menor privilégio:** publique o **Vault** (`:8200`) como um
> Resource **separado**, associado apenas a um grupo de administradores — nunca
> ao `ppgia95-validacao`. O PPGIA95 precisa falar apenas com o servidor IoT; o
> acesso direto ao Vault não deve ser concedido ao ambiente de testes.

---

## 5. Como isto se encaixa no fluxo IoT-TPM

1. O dispositivo IoT é provisionado por `iot-tpm/.../scripts/init_device.sh`:
   uma **semente TOTP aleatória** é gerada, **selada no TPM do dispositivo** e
   **registrada no Vault** do PPGIA96 (por `device_id`).
2. O servidor IoT (PPGIA96) lê a semente do Vault e valida o TOTP.
3. Toda a comunicação entre o cliente (PPGIA95) e o servidor (PPGIA96) trafega
   **através do Twingate**: sem o acesso ZTNA concedido, os endpoints do
   servidor IoT e o Vault são inalcançáveis.

Consulte os READMEs de [`iot-tpm/`](../iot-tpm/README.md) e
[`vault-tpm/`](../vault-tpm/README.md) para os detalhes de provisionamento e do
gerenciamento de segredos.

---

## 6. Referências

- Twingate — Deploy Connector via Docker:
  <https://www.twingate.com/docs/docker>
- Twingate — Connectors (visão geral):
  <https://www.twingate.com/docs/connectors>
