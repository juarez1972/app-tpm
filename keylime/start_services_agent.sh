cd keylime_agent_setup

# Parar serviços existentes
docker stop keylime-agent vault-server 2>/dev/null
docker rm keylime-agent vault-server 2>/dev/null

# Iniciar Vault
docker run -d \
  --name vault-server \
  --network host \
  registry.access.redhat.com/ubi8/ubi:latest \
  sh -c "dnf install -y wget unzip && wget -q https://releases.hashicorp.com/vault/1.15.0/vault_1.15.0_linux_amd64.zip -O /tmp/vault.zip && unzip -q /tmp/vault.zip -d /usr/local/bin && chmod +x /usr/local/bin/vault && mkdir -p /vault/data && vault server -dev -dev-root-token-id=root -dev-listen-address=0.0.0.0:8200"

# Aguardar Vault
sleep 15

# Iniciar Agent
docker run -d \
  --name keylime-agent \
  --network host \
  --privileged \
  -v $(pwd)/keylime-agent-config/agent.conf:/etc/keylime/agent.conf \
  keylime_agent_setup_keylime-agent \
  python3.9 -m keylime.cmd.agent
