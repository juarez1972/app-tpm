Este arquivo **README.md** foi estruturado para servir como o guia mestre da sua Prova de Conceito (PoC). 
Ele organiza a separação dos serviços em dois domínios (Identidade e Rede Zero Trust) e explica como eles se conectam para suportar a escala de 14 mil usuários.

---

# PoC: Migração VPN para ZTNA com OpenZiti & Keycloak

Este projeto implementa uma infraestrutura de **Zero Trust Network Access (ZTNA)** para substituir sistemas de VPN tradicionais (OpenVPN/OPNsense). A solução utiliza **OpenZiti** para a malha de rede segura e **Keycloak** (federado ao Entra ID) para gestão de identidades com auto-provisionamento.

## 1. Arquitetura da Solução

A PoC é dividida em dois arquivos de orquestração independentes:

* **`docker-compose-keycloak.yml`**: Camada de Identidade (IdP). Responsável pela autenticação e emissão de tokens JWT.
* **`docker-compose-openziti.yml`**: Camada de Rede (Control & Data Plane). Responsável por autorizar o acesso aos serviços baseando-se na confiança do token do Keycloak.

---

## 2. Descrição dos Serviços

### Camada de Identidade (`keycloak-db` & `keycloak`)

* **Keycloak**: Atua como o *Identity Broker*. Ele recebe as requisições de login, delega a autenticação para o **Microsoft Entra ID** via OIDC/SAML e emite um JWT assinado para o OpenZiti.
* **PostgreSQL**: Banco de dados persistente para armazenar configurações de Realms, Clients e metadados de usuários.

### Camada Zero Trust (`ziti-controller` & `ziti-edge-router`)

* **Ziti Controller**: O "cérebro" da rede. Gerencia as políticas de acesso e valida os tokens JWT do Keycloak. Em produção (14k usuários), este componente opera em cluster HA.
* **Ziti Edge Router**: O "braço" da rede. Funciona como o gateway de entrada para os usuários. Ele não possui portas de entrada abertas para a internet pública (com exceção da porta de link), tornando a rede "invisível".
* **Ziti Admin Console (ZAC)**: Interface gráfica para gestão da malha, disponível na porta `8443`.

---

## 3. Configuração do Ambiente

### Passo 1: Subir a Infraestrutura

```bash
# Iniciar o Keycloak
docker-compose -f docker-compose-keycloak.yml up -d

# Iniciar o OpenZiti
docker-compose -f docker-compose-openziti.yml up -d

```

### Passo 2: Configurar o Auto-Enrollment (Escalabilidade)

Para suportar os 14.000 usuários sem criação manual, execute o script de automação no Controller:

1. **JWT Signer**: Registra a chave pública do Keycloak no Ziti.
2. **Auth Policy**: Define o Keycloak como método primário de entrada.
3. **Auto-Enrollment**: Habilita a criação automática da "identidade" no Ziti no primeiro login do usuário via Entra ID.

---

## 4. Fluxo de Acesso do Usuário

1. O usuário abre o **Ziti Desktop Edge**.
2. Seleciona "Autenticação via Provedor Externo".
3. É redirecionado para o login da Microsoft (Entra ID).
4. Após o sucesso, o OpenZiti verifica se o e-mail do usuário possui permissão (**Service Policy**).
5. O acesso ao recurso interno é liberado sem exposição de IPs ou portas no firewall.

---

## 5. Considerações para Produção (14k Usuários)

| Item | Recomendação PoC | Recomendação Produção |
| --- | --- | --- |
| **Banco de Dados** | Docker Volume (Local) | DB Gerenciado (RDS/Azure SQL) |
| **Alta Disponibilidade** | Única Instância | Cluster de 3 Controllers (Raft) |
| **Distribuição** | Localhost | 4 Sites Geográficos com Edge Routers locais |
| **Certificados** | Auto-assinados | PKI Corporativa ou Let's Encrypt |

---
6. Integração de Grupos: Keycloak + Entra ID + OpenZiti

Para gerenciar 14 mil usuários, utilizaremos Policies baseadas em Claims. O objetivo é que o OpenZiti leia o grupo "Financeiro" vindo do Entra ID e conceda acesso automaticamente.
A. No Keycloak (Mapeamento do Entra ID)

    Vá em Identity Providers > Entra ID (seu provedor configurado).

    Acesse a aba Mappers.

    Crie um novo Mapper:

        Name: claim-groups-from-azure

        Mapper Type: Attribute Importer

        Social Attribute: groups (ou o nome da claim enviada pelo Azure).

        User Attribute Name: groups

B. No Keycloak (Inclusão no Token JWT)

    Vá em Client Scopes e crie um escopo chamado ziti-permissions.

    Em Mappers, adicione um User Attribute:

        User Attribute: groups

        Token Claim Name: roles (o OpenZiti costuma ler esta claim para autorização).

        Multivalued: On

    Associe este Client Scope ao seu Client do OpenZiti como "Default".

C. No OpenZiti (Posture Checks)

Agora, configuramos o OpenZiti para exigir que a claim roles contenha o valor específico para liberar um serviço.
Bash

# 1. Criar um Posture Check que valida o grupo dentro do JWT
ziti edge create posture-check ext-jwt "check-financeiro" \
  --signer-name "keycloak-automation" \
  --claims-property "roles" \
  --claims-value "id-do-grupo-azure-financeiro"

# 2. Criar uma Service Policy que une o Posture Check ao serviço
ziti edge create service-policy "acesso-financeiro-restrito" Dial \
  --identity-roles "#external-users" \
  --service-roles "#financeiro-services" \
  --posture-check-roles "check-financeiro"

Por que esta abordagem é vital para 14k usuários?

    Zero Toque no Ziti: Se o RH move um usuário de "Vendas" para "Financeiro" no Entra ID, o próximo JWT emitido pelo Keycloak terá a nova claim. O OpenZiti atualizará o acesso em tempo real sem você abrir o console.

    Segurança Granular: Mesmo que um usuário consiga "burlar" a identidade, ele não terá o Posture Check (a claim assinada pelo Keycloak), e o Edge Router cortará a conexão no nível do pacote.

    Auditoria: Os logs do Ziti mostrarão exatamente qual ext-jwt permitiu aquele acesso, facilitando conformidade com a LGPD/GDPR.
