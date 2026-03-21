# 🚀 Portal Proxy Seguro (SSO Google IDP)

Este projeto implementa um **Portal de Aplicações Internas** utilizando Python (Flask) como um Proxy Reverso autenticado. Ele permite que colaboradores acessem ferramentas restritas da rede corporativa de forma segura, utilizando suas contas Google como chave de acesso (Single Sign-On).

---

## 🏗️ Estrutura do Projeto

* **`deploy.sh`**: Script de automação que prepara o ambiente, valida o `.env` e gera certificados SSL.
* **`docker-compose.yml`**: Orquestrador que isola a rede interna e define os serviços (Proxy + Apps).
* **`.env`**: Arquivo de configuração centralizado para segredos e definições de domínio.
* **`proxy/app.py`**: O "cérebro" da aplicação. Gerencia OAuth2, permissões por domínio e o túnel de dados.
* **`proxy/templates/dashboard.html`**: A interface visual (Painel de Ícones estilo Google Workspace).
* **`proxy/certs/`**: Repositório dos certificados de criptografia HTTPS (Gerados automaticamente).

---

## ⚙️ Configuração do arquivo `.env`

Crie este arquivo na raiz do projeto para isolar as configurações sensíveis:

```env
# Domínio que o usuário digita no navegador
EXTERNAL_DOMAIN=ubuntuserverjuarez.com

# Regras de Acesso
ALLOWED_LOGIN_DOMAIN=gmail.com
ALLOWED_USERS=admin@empresa.com,diretoria@gmail.com

# Credenciais Google Cloud (OAuth 2.0 Client ID)
GOOGLE_CLIENT_ID=seu_id_aqui.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu_secret_aqui

# Segurança Flask
FLASK_SECRET=uma_string_longa_e_aleatoria

# 🚀 Guia de Deploy Passo a Passo

##1. Preparação no Google Cloud

    Acesse o Google Cloud Console.

    Vá em APIs e Serviços > Credenciais.

    Crie um ID do cliente OAuth 2.0 (Tipo: Aplicativo Web).

    Configure as URLs rigorosamente:

        Origens JavaScript autorizadas: https://ubuntuserverjuarez.com

        URIs de redirecionamento autorizados: https://ubuntuserverjuarez.com/callback

    Copie o ID e a Chave Secreta para o seu arquivo .env.

##2. Configuração do Host Local (DNS de Teste)

Como o domínio ubuntuserverjuarez.com ainda não está registrado, você deve "enganar" seu sistema operacional:

    Linux/Mac: No terminal, rode sudo nano /etc/hosts -> Adicione a linha: 127.0.0.1 ubuntuserverjuarez.com

    Windows: Abra o Bloco de Notas como Administrador no caminho C:\Windows\System32\drivers\etc\hosts e adicione a mesma linha.

##3. Organização de Arquivos

Certifique-se de que a estrutura de pastas está correta:

    proxy/app.py (Código Python)

    proxy/templates/dashboard.html (Interface)

    deploy.sh (Na raiz do projeto)

##4. Execução do Deploy

No terminal, na raiz do projeto, execute os comandos:
Bash

chmod +x deploy.sh
./deploy.sh

O script irá gerar os certificados SSL autoassinados, construir a imagem Docker e subir os serviços em background.
#➕ Adicionando Novas Aplicações para Publicação

O portal é expansível e dinâmico. Para publicar um novo site interno:

    No docker-compose.yml: Adicione o novo serviço na rede backend (sem expor portas externas):
    YAML

    meu-novo-servico:
      image: minha-app-interna
      networks:
        - backend

    No proxy/app.py: Adicione uma nova entrada no dicionário APPLICATIONS:
    Python

    "minha-app": {
        "name": "Nome Amigável",
        "url": "http://meu-novo-servico:porta",
        "icon": "[https://url-do-icone.png](https://url-do-icone.png)"
    }

    Reinicie: Execute ./deploy.sh para aplicar as mudanças e atualizar o dashboard.

#🛡️ Auditoria e Logs de Segurança

O sistema registra todas as atividades críticas para monitoramento. Você pode acompanhar quem está acessando em tempo real através do Docker.

Comando de Monitoramento:
Bash

docker logs -f proxy-flask

Principais Eventos Registrados:

    AUDIT - LOGIN SUCESSO: Nome e e-mail de quem autenticou via Google.

    AUDIT - ACESSO APP: Identifica qual usuário entrou em qual aplicação interna (Ex: usuario@gmail.com -> nginx-interno/index.html).

    AUDIT - NEGADO: Registra tentativas de acesso de e-mails que não pertencem ao domínio permitido ou à lista do .env.

#⚠️ Observações de Segurança

    Certificados HTTPS: Os arquivos gerados são autoassinados. O navegador exibirá um alerta de "Conexão Não Segura"; aceite o risco para testar localmente. Em produção, utilize certificados válidos.

    Isolamento de Rede: As aplicações internas (como o Nginx padrão) não possuem acesso direto da internet. O único "portão de entrada" é o Proxy Flask na porta 443.
