# keylime-agent-custom/Dockerfile

# Baseia-se na imagem oficial do agente Rust
FROM quay.io/keylime/keylime_agent:master

# Muda para o usuário root para instalar pacotes
USER root

# CORREÇÃO: Usa 'apk add' (para Alpine) em vez de 'apt-get'
# A flag --no-cache atualiza, instala e limpa em um único passo.
RUN apk add --no-cache curl jq

# Retorna ao usuário 'keylime' padrão para segurança
USER keylime
