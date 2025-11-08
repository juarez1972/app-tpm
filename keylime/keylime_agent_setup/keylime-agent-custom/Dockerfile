# keylime-agent-custom/Dockerfile

# Baseia-se na imagem oficial do agente Rust
FROM quay.io/keylime/keylime_agent:master

# Muda para o usuário root para instalar pacotes
USER root

# CORREÇÃO: Usa 'dnf' (para Fedora/RHEL)
RUN dnf install -y curl jq && \
    dnf clean all

# Retorna ao usuário 'keylime' padrão para segurança
USER keylime
