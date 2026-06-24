# Arquitetura para Integração da Proteção de Segredos com Hardware e Software

Este projeto apresenta uma arquitetura de referência para a gestão e proteção de segredos (credentials, chaves, certificados), integrando de forma holística camadas de hardware e software. A solução é focada em ambientes de alta criticidade, onde a proteção de dados em repouso, em trânsito e em uso é fundamental.

## 1. Visão Geral

A arquitetura baseia-se na premissa de que a segurança baseada apenas em software é insuficiente. Ao ancorar a confiança no hardware (**TPM 2.0**) e estender essa confiança através de redes **Zero Trust** e cofres de senhas (**Vault**), criamos uma barreira robusta contra exfiltração de dados e acessos não autorizados.

## 2. Pilares de Segurança

### 🛡️ Proteção via Hardware (TPM 2.0)
* **Root of Trust:** Utilização do *Trusted Platform Module* para gerar e armazenar chaves criptográficas que nunca deixam o hardware.
* **Sealing:** Segredos do sistema são "selados" para o estado específico do hardware (PCRs), garantindo que só sejam acessíveis se o sistema não tiver sido adulterado.

### 🔐 Gestão de Segredos (HashiCorp Vault)
* **Centralização:** Gestão dinâmica de segredos com políticas de acesso estritas.
* **Integração:** O Vault utiliza o TPM para proteger sua própria chave mestra (*unseal key*), eliminando a necessidade de intervenção humana no boot.

### 🌐 Conectividade Zero Trust
* **Rede Invisível:** Implementação via **OpenZiti** ou **Twingate**, garantindo que os serviços de segredos não possuam portas expostas na internet pública.
* **Identidade Forte:** Cada componente da arquitetura possui uma identidade criptográfica única.

### 🔑 Autenticação e Integridade (HOTP & HMAC)
* **Segundo Fator (HOTP):** Uso de *HMAC-based One-Time Password* para validação adicional em fluxos críticos de acesso.
* **Ofuscação e Assinatura (HMAC):** Aplicação de HMAC para garantir a integridade das mensagens e ofuscar segredos em trânsito, impedindo ataques de *man-in-the-middle*.

### 🚀 Roadmap: TEE com Intel TDX
* **Proteção em Uso:** Planejamento para a implementação de *Trust Domain Extensions* (TDX) para isolar cargas de trabalho em hardware, protegendo os segredos mesmo contra administradores do host ou hipervisores comprometidos.

## 3. Tecnologias Utilizadas
* **Segurança de Hardware:** TPM 2.0, Intel TDX (em desenvolvimento).
* **Software de Segurança:** HashiCorp Vault, OpenZiti, Twingate.
* **Protocolos:** HOTP (RFC 4226), HMAC (RFC 2104), OIDC.
* **Infraestrutura:** Docker, Terraform, Python, Shell Script.

## 4. Configuração e Instalação
### Pré-requisitos
* Sistema com suporte a TPM 2.0 (ou simulador `swtpm`).
* Docker e Docker Compose instalados.
* Bibliotecas `tss2` para interação com o hardware.

* Criar ambiente virtual para o Python
    $ cd caminho/do/projeto
    $ python -m venv .venv
    $ source .venv/bin/activate
    $ pip install -r requirements.txt
    para desativar: deactivate

## 4.1. Suporte ao TPM no host linux:  
    Habilite o TPM na máquina virtual ou na Bios, se for o caso.
    Instale os pacotes necessários:
    $ sudo apt update
    $ sudo apt install tpm2-tools
    No Ubuntu/Linux você consegue verificar se o TPM está presente e habilitado usando alguns arquivos do sistema e comandos simples no terminal.
    Verificando se o TPM existe
    Use um destes comandos (pode rodar todos, se quiser):
    Ver se existe dispositivo TPM 2.0 no sysfs:
    $ ls /sys/class/tpm/
    Se aparecer algo como tpm0 ou tpmrm0, há TPM disponível.
    Ver se o diretório de segurança do TPM existe:
    $ [[ -d $(ls -d /sys/kernel/security/tpm* 2>/dev/null | head -1) ]] && echo "TPM disponível" || echo "TPM ausente".
    Ver dispositivos de caractere TPM em /dev:
    $ ls /dev/tpm*
    Se aparecer /dev/tpm0 e/ou /dev/tpmrm0, o kernel detectou o TPM.

* Verificando módulos do kernel TPM
    Confira se os módulos do kernel relacionados a TPM estão carregados:
    $ lsmod | grep tpm.
    Se aparecer linhas como tpm_tis, tpm_tis_core, tpm, tpm_crb etc., o suporte ao TPM está ativo no kernel.
* Verificando via ferramentas TPM2
    Se você já instalou o pacote tpm2-tools, pode ainda fazer:
    $ sudo tpm2_getrandom 4 — se retornar bytes, o TPM está funcional.
    $ sudo tpm2_getcap properties-fixed | head — mostra capacidades e versão do TPM.

## 4.2. Suporte ao SGX no host linux:
    O processo envolve três grandes etapas: verificar suporte no hardware/BIOS, instalar driver/SDK/PSW do SGX e rodar amostras de teste para validar a instalação no Ubuntu  24.04.
*   1. Pré‑requisitos e checagens
    Verifique se a CPU suporta SGX (procure “sgx” nas flags da CPU ou use ferramentas como o repositório SGX-hardware).
    No BIOS/UEFI, habilite SGX (modo Enabled ou Software Controlled) e desative Secure Boot se o driver não for assinado.
    Garanta um kernel compatível e headers instalados, pois o módulo de kernel do SGX precisa casar com a versão do kernel (linux-headers-$(uname -r)).
 *  2. Instalação do driver SGX
    Instale ferramentas de compilação necessárias (build‑essential, dkms, etc.), que são usadas para construir e carregar o módulo SGX no kernel.
    Baixe o driver DCAP mais recente para sua distro (por exemplo via sgx_linux_x64_driver_${version}.bin do site da Intel) e execute o instalador com privilégios de administrador.
    Como alternativa, clone o repositório intel/linux-sgx-driver, compile com make e copie o módulo isgx.ko para /lib/modules/$(uname -r)/kernel/drivers/intel/sgx, rodando depmod e modprobe isgx para carregar o módulo.
    Verifique se o driver está ativo observando lsmod | grep sgx e a existência de dispositivos como /dev/isgx ou /dev/sgx/enclave, conforme a versão do driver.
*   3. Instalação do SDK e PSW
    Instale dependências de desenvolvimento (ocaml, automake/autoconf, cmake, python3, libssl‑dev, libcurl4‑openssl‑dev, libprotobuf‑dev, etc.), usadas para compilar o SDK e serviços de plataforma.
    Clone o repositório intel/linux-sgx, execute make preparation para baixar toolchains adicionais e copiar ferramentas específicas para Ubuntu (por exemplo, scripts em external/toolset/ubuntu20.04 para /usr/local/bin).
    Baixe e execute o instalador do SDK (sgx_linux_x64_sdk_${version}.bin) apontando para um diretório, geralmente /opt/intel/sgxsdk, e depois carregue o ambiente com source /opt/intel/sgxsdk/environment.
    Instale o PSW e os serviços de lançamento/atestado (pacotes como libsgx-urts, libsgx-launch, libsgx-epid, libsgx-quote-ex a partir do repositório APT da Intel SGX).

*  4. Testes funcionais básicos
    Use um teste simples de hardware, como o projeto SGX-hardware (test-sgx.c), compilando e executando para confirmar que a CPU, BIOS e driver estão corretos.
    No diretório SampleCode do SDK (por exemplo SampleEnclave ou LocalAttestation), faça make e rode o binário ./app para verificar se enclaves são criados em modo real ou simulado (SGX_MODE=HW ou SGX_MODE=SIM).
    Confirme que o serviço AESM (serviço de atestado da Intel) está rodando e escutando seu socket, pois vários exemplos de atestação remota dependem dele para funcionar corretamente.
*  5.   Testes de SGX dentro da VM
    Confirme se o driver está carregado no guest com dmesg | grep sgx e verificando se há dispositivos SGX (/dev/isgx ou /dev/sgx/enclave), o que indica que o kernel da VM está vendo a funcionalidade.
    Compile e rode amostras do SDK (por exemplo repositórios de tutorial como intel-sgx-enclave-ubuntu-tutorial) dentro da VM, usando make e executando ./app para verificar criação de enclaves.
    Caso apenas o modo simulado esteja disponível, ajuste a variável de ambiente SGX_MODE=SIM ao compilar/rodar os exemplos, o que permite desenvolver e testar sem acesso direto a SGX hardware.

*  6. Validações adicionais e troubleshooting
    Se o driver não carrega, verifique novamente compatibilidade de kernel, opções de SGX no BIOS e mensagens de log do kernel relacionadas a SGX.
    Para problemas com enclaves falhando ou erros de atestação, consulte o guia de instalação oficial Intel SGX para Linux, que traz uma sequência detalhada de validações e erros comuns.
    Em ambientes com containers, ajuste mapeamentos de dispositivo (/dev/isgx ou /dev/sgx/enclave) e permissões de segurança do Docker/Podman conforme indicado em tutoriais de SGX com containers.
   
## 5. Arquitetura Lógica
1.  **Boot:** O sistema valida o estado do firmware via TPM.
2.  **Unseal:** O serviço de Segredos (Vault) solicita a chave de descriptografia ao TPM.
3.  **Auth:** O usuário/serviço autentica-se via Zero Trust + HOTP.
4.  **Transaction:** Os dados são trocados utilizando HMAC para garantir que não houve alteração no percurso.

## 6. Licença

Este projeto está licenciado sob a Licença MIT - consulte o arquivo [LICENSE](LICENSE) para detalhes.

---
**Desenvolvido pelos pesquisdores da PUC-PR
1. ** [Juarez de Oliveira, M.Sc.] juarez.oliveira@pucpr.edu.br
2. ** [Juliano Sartori Langaro, M.Sc.] juliano.langaro@pucpr.edu.br
3. ** [Fellipe Medeiros Veiga, M.Sc.] fellipe.veiga@pucpr.edu.br
4. ** [Altair Olivo Santin, PhD.] altair.santin@pucpr.br *Orientador

