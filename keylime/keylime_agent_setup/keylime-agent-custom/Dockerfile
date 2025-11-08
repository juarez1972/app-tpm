# keylime-agent-custom/Dockerfile

# Baseia-se na imagem oficial do agente Rust (baseada em RHEL/Fedora)
FROM quay.io/keylime/keylime_agent:master

# Muda para o usuário root para instalar pacotes
USER root

# Instala os pacotes 'dnf' (para RHEL/Fedora)
RUN dnf install -y curl jq && \
    dnf clean all

# --- CORREÇÃO DE PERMISSÃO ---
# Adiciona o usuário 'keylime' (que existe na imagem base)
# ao grupo 'tss' (que também existe) para permitir acesso ao TPM.
RUN usermod -a -G tss keylime

# Retorna ao usuário 'keylime' padrão para segurança
USER keylime
