Com a nova estrutura de rede compartilhada e a correção das portas, o seu `README.md` precisa refletir a arquitetura exata da PoC. Este documento agora serve como o guia operacional para subir o ambiente e validar a integração.

# Antes de tudo, vamos subir e testar o Openziti sozinho
Edite um arquivo .env e ajuste a senha e o que mais quiser


    # OpenZiti Variables
    ZITI_IMAGE=openziti/quickstart
    ZITI_VERSION=latest

    # the user and password to use
    # Leave password blank to have a unique value generated or set the password explicitly
    ZITI_USER=admin
    ZITI_PWD=Coloque_senha_segura

    ZITI_INTERFACE=0.0.0.0

    # controller name, address/port information
    ZITI_CTRL_NAME=ziti-controller
    ZITI_CTRL_EDGE_ADVERTISED_ADDRESS=ziti-edge-controller
    ZITI_CTRL_ADVERTISED_ADDRESS=ziti-controller
    #ZITI_CTRL_EDGE_IP_OVERRIDE=10.10.10.10
    #ZITI_CTRL_EDGE_ADVERTISED_PORT=8441
    #ZITI_CTRL_ADVERTISED_PORT=8440

    # The duration of the enrollment period (in minutes), default if not set. shown - 7days
    ZITI_EDGE_IDENTITY_ENROLLMENT_DURATION=10080
    ZITI_ROUTER_ENROLLMENT_DURATION=10080

    # router address/port information
    #ZITI_ROUTER_NAME=ziti-edge-router
    #ZITI_ROUTER_ADVERTISED_ADDRESS=ziti-edge-router
    #ZITI_ROUTER_PORT=8442
    #ZITI_ROUTER_IP_OVERRIDE=10.10.10.10
    #ZITI_ROUTER_LISTENER_BIND_PORT=8444
    #ZITI_ROUTER_ROLES=public

Agora execute o docker-compose:
    $docker-compose -f docker-compose-openziti up -d

Acesse via web para concluir as configurações, usando a senha que está no .env:
    https://ipdamaquina:8443/login


---

# PoC: Migração VPN para ZTNA com OpenZiti & Keycloak

Este projeto implementa uma infraestrutura de **Zero Trust Network Access (ZTNA)**. O objetivo é validar a substituição de VPNs baseadas em perímetro (como OPNsense) por uma rede overlay baseada em identidade, capaz de escalar para 10.000 usuários.

## 1. Topologia da Rede Docker

Os serviços estão separados para permitir escalabilidade independente, mas utilizam uma rede compartilhada para comunicação segura entre o plano de controle e o provedor de identidade.

---

## 2. Estrutura de Portas e Acessos

| Serviço | Porta Externa | URL de Acesso | Descrição |
| --- | --- | --- | --- |
| **Ziti Controller** | `1280` | `https://localhost:1280` | API principal e registro de clientes. |
| **Ziti Admin Console** | `8444` | `https://localhost:8444` | Interface gráfica de gestão (ZAC). |
| **Keycloak Web** | `8080` | `http://localhost:8080` | Painel de administração do IdP. |
| **Keycloak HTTPS** | `8443` | `https://localhost:8443` | Reservado para uso com certificados TLS. |

---

## 3. Preparação e Execução

### Passo 1: Criar a rede compartilhada

Antes de iniciar os containers, a rede externa deve existir:

```bash
docker network create ziti-shared-net

```

### Passo 2: Iniciar os serviços

Suba os arquivos em terminais separados ou em sequência:

```bash
# Iniciar Camada de Identidade
docker-compose -f docker-compose-keycloak.yml up -d

# Iniciar Camada Zero Trust
docker-compose -f docker-compose-openziti.yml up -d

```

---

## 4. Configuração do Auto-Enrollment (Escala de k usuários)

Para automatizar a entrada de usuários vindos do **Entra ID** via Keycloak, execute o comando abaixo dentro do container do Controller.

> **Nota:** Utilizamos o DNS interno `http://keycloak:8080` para o Ziti buscar as chaves (JWKS), enquanto o `issuer` aponta para onde o usuário final autentica.

```bash
docker exec -it ziti-controller ziti edge create ext-jwt-signer "keycloak-automation" \
  --claims-property "email" \
  --issuer "http://localhost:8080/realms/ziti-realm" \
  --jwks-endpoint "http://keycloak:8080/realms/ziti-realm/protocol/openid-connect/certs" \
  --external-id-claim "email" \
  --auto-enrollment-enabled

```

---

## 5. Mapeamento de Grupos (Entra ID -> Ziti)

Para que a autorização seja dinâmica, configure no Keycloak:

1. **Client Scope**: Crie um escopo que mapeie os grupos do Azure para uma claim chamada `roles` no JWT.
2. **OpenZiti Posture Check**: Crie um check do tipo `ext-jwt` que valide se o valor "Financeiro" está presente na claim `roles`.

---

## 6. Próximos Passos para Validação

* [ ] **Teste de Conectividade**: Validar se o Controller alcança o endpoint do Keycloak:
`docker exec ziti-controller curl -v http://keycloak:8080/realms/ziti-realm`
* [ ] **Provisionamento**: Realizar o primeiro login com um usuário de teste e verificar se a identidade foi criada automaticamente no console (`https://localhost:8444`).
* [ ] **Substituição da VPN**: Configurar um serviço simples (ex: um servidor web interno) e tentar acessá-lo via Ziti Desktop Edge sem estar na rede local.

---


