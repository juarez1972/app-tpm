# keylime-agent-custom/Dockerfile

# Baseia-se na imagem oficial do agente Rust [3, 24, 27]
FROM quay.io/keylime/keylime_agent:master

# Muda para o usuário root para instalar pacotes
USER root

# Atualiza e instala curl e jq [26, 27]
# Assume uma base Debian/Ubuntu
RUN apt-get update && \
    apt-get install -y curl jq && \
    rm -rf /var/lib/apt/lists/*

# Retorna ao usuário 'keylime' padrão para segurança
USER keylime
