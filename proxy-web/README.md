# 🚀 Portal Proxy Autenticado (Google IDP)

Este projeto é um **Proxy Reverso Autenticado** desenvolvido em Python com **Flask** e **Gunicorn**, rodando em containers **Docker**. Ele permite expor aplicações da rede interna da empresa para a internet de forma segura, utilizando o Google como provedor de identidade (IDP).

## 📋 Funcionalidades

*   **Autenticação Google OAuth2**: Apenas usuários autorizados acessam o portal.
*   **Dashboard Visual**: Interface estilo "Google Workspace" com ícones para cada aplicação.
*   **Controle de Acesso Flexível**: Permissão por domínio (ex: `@gmail.com`) ou e-mails específicos via `.env`.
*   **Segurança HTTPS**: Terminação SSL nativa no Proxy usando certificados (autoassinados ou oficiais).
*   **Logs de Auditoria**: Registro de quem acessou, qual aplicação e em qual horário.
*   **Arquitetura Isolada**: Aplicações internas ficam em uma rede Docker privada, sem exposição direta de portas.

## 🏗️ Estrutura do Projeto

```text
.
├── .env                # Variáveis de ambiente (Segredos e Configs)
├── docker-compose.yml  # Orquestração dos serviços (Proxy + Apps Internas)
├── deploy.sh           # Script de automação (Certs + Build)
├── proxy/
│   ├── app.py          # Lógica do Proxy e Autenticação
│   ├── Dockerfile      # Configuração da imagem Python/Gunicorn
│   ├── requirements.txt# Dependências Python
│   ├── certs/          # Certificados SSL (.pem)
│   └── templates/
│       └── dashboard.html # Interface visual do portal
