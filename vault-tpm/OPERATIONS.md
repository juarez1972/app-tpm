# Operação, Diagnóstico e Troubleshooting — vault-tpm

> Registro consolidado da sessão de depuração de 07/09/2026. Este documento complementa o `README.md` principal com procedimentos operacionais validados em produção neste host (`ep09-pucpr`, Podman rootless).

## Sumário

- [Ambiente e ferramentas](#ambiente-e-ferramentas)
- [Como testar o TPM](#como-testar-o-tpm)
- [Como recuperar o root token](#como-recuperar-o-root-token)
- [Como apagar tokens e reinicializar do zero](#como-apagar-tokens-e-reinicializar-do-zero)
- [Checklist de saúde da stack](#checklist-de-saúde-da-stack)
- [Histórico de incidentes resolvidos](#histórico-de-incidentes-resolvidos)

## Ambiente e ferramentas

Este projeto foi validado neste host rodando **Podman rootless** com o wrapper `docker-compose`/`docker compose`. Duas armadilhas de ferramenta identificadas:

- **Não use `docker-compose` v1.29.2 (Python, EOL)**. Ele tem um bug conhecido (`KeyError: 'ContainerConfig'`) ao recriar containers geridos pelo Podman, e falha silenciosamente ao remover redes/containers em estado "stopping", deixando resíduos que causam falsos positivos de porta ocupada.
- **Use o Compose v2 (binário Go)**. Verifique a versão antes de operar:

  ```bash
  docker compose version
  # Esperado: Docker Compose version v2.x.x (ou v5.x.x), não "1.29.2, build unknown"
  ```

  Se o host ainda tiver o binário legado em `/usr/bin/docker-compose`, substitua:

  ```bash
  mv /usr/bin/docker-compose /usr/bin/docker-compose.v1.bak
  curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/bin/docker-compose
  chmod +x /usr/bin/docker-compose
  docker compose version
  ```

## Como testar o TPM

### Verificar disponibilidade do TPM no host

```bash
ls /dev/tpm*                 # esperado: /dev/tpm0 e/ou /dev/tpmrm0
ls /sys/class/tpm/
lsmod | grep tpm
```

### Verificar atributos do SRK persistente

O SRK usado por este projeto fica no handle `0x81010001`. Ele **precisa** ter o atributo `userwithauth` habilitado — sem ele, qualquer `tpm2_create` de filhos (unseal keys, root token) falha com `TPM_RC_AUTH_UNAVAILABLE` (`0x12F`):

```bash
tpm2_readpublic -c 0x81010001 2>&1 | grep -A2 attributes
```

Saída esperada (correta):
```
attributes:
  value: fixedtpm|fixedparent|sensitivedataorigin|userwithauth|restricted|decrypt|noda
```

Saída **incorreta** (causa o erro `0x12F`):
```
attributes:
  value: fixedtpm|fixedparent|sensitivedataorigin|adminwithpolicy|restricted|decrypt
```

Se o SRK estiver com `adminwithpolicy` em vez de `userwithauth`, recrie-o:

```bash
tpm2_evictcontrol -C o -c 0x81010001
tpm2_createprimary -C o -G rsa2048 -c /tmp/primary.ctx \
  -a "fixedtpm|fixedparent|sensitivedataorigin|userwithauth|restricted|decrypt|noda"
tpm2_evictcontrol -C o -c /tmp/primary.ctx 0x81010001
tpm2_readpublic -c 0x81010001 2>&1 | grep -A2 attributes   # confirmar userwithauth
```

> Atenção: recriar o SRK invalida qualquer blob `.enc`/`.enc.pub`/`.enc.priv` previamente selado sob o handle antigo. É necessário reinicializar o Vault do zero depois desta operação (ver seção seguinte).

### Teste isolado de seal/unseal (sem tocar no Vault)

```bash
echo -n "teste" > /tmp/sealdata
tpm2_create -C 0x81010001 -u /tmp/test.pub -r /tmp/test.priv -i /tmp/sealdata
```

Se completar sem erro, o SRK está pronto para o `vault_initializer.py`.

### Teste de saúde via tpm-validator

```bash
curl -s http://127.0.0.1:8080/health | jq
docker logs tpm-validator --tail 30
```

### Script de verificação completa da stack

```bash
cd vault-tpm
bash system_status.sh
```

Ele reporta 9 verificações: Docker/Compose, containers, disponibilidade do TPM, status do Vault, autenticação TPM, rede, recursos do sistema, logs recentes e operações TPM básicas (leitura de PCR, propriedades). O item **"Container para serviço vault-initializer não encontrado"** é esperado e não é falha — o serviço tem `restart: "no"` e sai após concluir o seal/unseal com sucesso.

## Como recuperar o root token

Com a stack saudável e o Vault destravado, use o script dedicado — ele nunca grava o token em disco e não deixa rastro em log de container:

```bash
cd vault-tpm
TPM_DATA_DIR=./tpm-data ./scripts/get_root_token.sh
```

Para logar direto na CLI sem expor o token na linha de comando:

```bash
TPM_DATA_DIR=./tpm-data ./scripts/get_root_token.sh --quiet | vault login -
vault token lookup
```

Para acessar pela **UI web**: abra `http://<host>:8200/ui`, escolha o método **Token**, e cole o valor obtido por `./scripts/get_root_token.sh --quiet`. Validado nesta sessão com sucesso.

Depois do primeiro acesso, é recomendado revogar o root token e usar um de menor privilégio:

```bash
TPM_DATA_DIR=./tpm-data ./scripts/revoke_root_token.sh
```

## Como apagar tokens e reinicializar do zero

Use apenas quando as unseal keys/root token seladas no TPM estiverem inutilizáveis (ex.: SRK recriado, `tpm-data` corrompido, ou Vault selado sem chave recuperável).

```bash
docker compose down
rm -rf ./vault-data/*   # storage do Vault (dados e metadados do backend "file")
rm -rf ./tpm-data/*     # blobs .enc / .enc.pub / .enc.priv selados no TPM antigo
docker compose up -d
docker logs vault-initializer --tail 40   # deve mostrar "inicializando Vault (5 shares / threshold 3)…"
```

**Importante**: isso descarta permanentemente todos os segredos armazenados no Vault atual. Não há recuperação possível sem as unseal keys originais.

## Checklist de saúde da stack

Sequência de comandos para validar rapidamente se tudo está operacional:

```bash
docker compose ps
ss -tulpn | grep -E "8200|8080"
curl -s http://127.0.0.1:8200/v1/sys/health | jq
docker logs vault --tail 20
docker logs vault-initializer --tail 40
docker logs tpm-validator --tail 20
bash system_status.sh
```

Indicadores de stack saudável:
- `vault` com status `Up` estável (sem "Less than a second" recorrente).
- `vault-initializer` finalizado (`Exited (0)`) com a última linha `✅ Processo concluído: Vault operacional.`
- `curl /v1/sys/health` retornando JSON com `"sealed": false`.
- Nenhuma linha `Error initializing listener` nos últimos logs de `vault`.

## Histórico de incidentes resolvidos

Registro das causas raiz identificadas e corrigidas nesta sessão, para referência futura.

### 1. Porta 8200 mapeada incorretamente

**Sintoma**: Vault subia, mas a API não respondia na porta esperada.
**Causa**: `docker-compose.yml` publicava `"8201:8200"` (host 8201 → container 8200), divergindo do `listener` interno declarado em `0.0.0.0:8200`.
**Correção**: mapear `"8200:8200"` no serviço `vault`.

### 2. `cluster_addr` igual a `api_addr`

**Sintoma**: `bind: address already in use` mesmo com porta livre no host.
**Causa**: edição indevida deixou `cluster_addr = "http://vault:8200"` idêntico ao `api_addr`, causando conflito interno de listener.
**Correção**: manter `cluster_addr = "http://vault:8201"` (porta diferente da API), mesmo sem publicá-la no host.

### 3. `docker-compose.yml` sem indentação

**Sintoma**: edições no compose "não pegavam" ao subir a stack.
**Causa**: arquivo editado perdeu a indentação hierárquica do YAML (todos os campos no mesmo nível de `services:`), tornando o schema inválido.
**Correção**: reindentar o arquivo corretamente (2 espaços por nível) e validar com `docker compose config` antes de subir.

### 4. Duplicação de carregamento do `vault-config.hcl` (causa raiz principal do crash loop)

**Sintoma**: `Error initializing listener of type tcp: listen tcp4 0.0.0.0:8200: bind: address already in use`, reprodutível mesmo em execução isolada (`docker run --rm -it`, sem restart policy, sem volumes extras, sem containers concorrentes, HCL validado byte a byte).
**Causa raiz**: a imagem oficial `vault:1.13.3` já carrega automaticamente qualquer arquivo de configuração dentro de `/vault/config/` via `docker-entrypoint.sh`. O `docker-compose.yml` também especificava `command: server -config=/vault/config/vault-config.hcl`, fazendo o Vault processar o **mesmo arquivo duas vezes** na mesma execução — dois blocos `listener "tcp"` competindo pela porta dentro do próprio processo.
**Correção**: remover o `-config=` explícito do `command`, deixando apenas `command: server`. O entrypoint carrega `/vault/config/vault-config.hcl` automaticamente por já estar montado no diretório padrão.
**Diagnóstico intermediário descartado**: chegou-se a suspeitar de `conmon` órfão do Podman retendo a porta (confirmado uma vez, via `ss -tulpn | grep 8200` mostrando processo `conmon` vivo sem container correspondente) — matar o PID resolveu temporariamente, mas o crash loop subjacente (causa 4) continuava gerando novos órfãos a cada ciclo.

### 5. `docker-compose` v1.29.2 gerando estado inconsistente

**Sintoma**: `ERROR: for vault 'ContainerConfig'` / `KeyError: 'ContainerConfig'` ao recriar containers; containers presos em estado "stopping" impossíveis de remover; rede `vault-tpm_vault-network` não removível ("has associated containers").
**Causa**: bug conhecido do `docker-compose` v1.29.2 (Python, EOL) ao interpretar metadata de imagem gerenciada pelo Podman.
**Correção**: substituir o binário por Compose v2 (Go) — ver seção "Ambiente e ferramentas". Estado travado foi limpo com `podman kill`/`podman rm -f`/`podman network rm -f` diretamente, contornando o compose v1.

### 6. SRK persistente sem `userwithauth` (bloqueava o seal das chaves no TPM)

**Sintoma**: `vault-initializer` conectava ao Vault, iniciava o `sys/init`, mas falhava ao selar a unseal key 0 no TPM: `ERROR: Esys_Create(0x12F) - tpm:error(2.0): authValue or authPolicy is not available for selected entity`. Nas tentativas seguintes, o Vault ficava **inicializado e selado sem nenhuma chave de unseal recuperável** (estado órfão).
**Causa raiz**: o SRK persistente no handle `0x81010001` tinha o atributo `adminwithpolicy` em vez de `userwithauth`, exigindo sessão de política para qualquer `tpm2_create` de filho — incompatível com o modo de autorização simples usado pelo `vault_initializer.py`.
**Correção**: `tpm2_evictcontrol` para liberar o handle, seguido de `tpm2_createprimary` com atributos explícitos incluindo `userwithauth`, e `tpm2_evictcontrol` para tornar persistente de novo no mesmo handle. Ver comandos completos na seção "Como testar o TPM".
**Consequência**: como as chaves da tentativa anterior nunca foram persistidas com sucesso, foi necessário resetar `./vault-data` e `./tpm-data` e reinicializar o Vault do zero (seção "Como apagar tokens e reinicializar do zero").

### Resultado final validado

Após as correções 1 a 6, a sequência completa de inicialização foi executada com sucesso e é reproduzível:

```
[vault-init] ✅ unseal key 0..4 seladas no TPM
[vault-init] ✅ root token selado no TPM (não gravado em texto claro).
[vault-init] 🎉 Vault DESTRAVADO com sucesso.
[vault-init] ✅ Processo concluído: Vault operacional.
```

Root token recuperado com sucesso via `TPM_DATA_DIR=./tpm-data ./scripts/get_root_token.sh` e utilizado para login na UI web (`http://<host>:8200/ui`), confirmando o fluxo de auto-unseal via TPM ponta a ponta neste host.
