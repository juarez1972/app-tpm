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

## 4.3. Suporte ao TDX no host linux:
    Para instalar e habilitar Intel TDX em um host Ubuntu 24.04, você precisa de hardware compatível (Xeon com TDX), BIOS configurada, kernel/stack TDX instalados e um stack de virtualização (QEMU/libvirt) preparado para criar e rodar VMs confidenciais (TDs). [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

*  1. Pré‑requisitos de hardware e sistema
- Use processadores Intel Xeon com suporte a TDX (Sapphire Rapids, Emerald Rapids, Xeon 6, etc.). [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
- Instale Ubuntu Server 24.04 LTS “puro” (imagem genérica) como sistema base no host. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
- Certifique‑se de que o firmware/BIOS do servidor suporta TME/TME‑MT/TDX; isso normalmente aparece em servidores recentes com Xeon de 4ª geração ou mais novos. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

Exemplo de comando para atualizar o sistema antes de começar:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

*  2. Habilitar TDX na BIOS
Entre na BIOS/UEFI do servidor e ative as opções de criptografia de memória e TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
Os nomes exatos variam, mas a documentação da Canonical/Intel sugere algo nesta linha: [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)

    Na seção de CPU / Processor / Socket Configuration:

    - Memory Encryption (TME) → Enable  
    - Total Memory Encryption Bypass → Enable (opcional, melhora desempenho de VMs normais). [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - Total Memory Encryption Multi‑Tenant (TME‑MT) → Enable. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    - TME‑MT memory integrity → Disable. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - Trust Domain Extension (TDX) → Enable. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    - TDX Secure Arbitration Mode Loader (SEAM Loader) → Enable (permite carregar TDX Module via BIOS/ESP). [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - TME‑MT/TDX key split → algum valor não zero. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    Na seção SGX:
    - SW Guard Extensions (SGX) → Enable. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    Salve e reinicie o servidor. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)

*  3. Habilitar TDX no kernel (parâmetros de boot)
No Ubuntu 24.04, você precisa ativar TDX no módulo KVM/intel com parâmetros de kernel. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

    1. Edite `/etc/default/grub`:
    ```bash
    sudo nano /etc/default/grub
    ```

    2. Em `GRUB_CMDLINE_LINUX_DEFAULT`, adicione:
    ```text
    nohibernate kvm_intel.tdx=1
    ```

    Exemplo:
    ```text
    GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nohibernate kvm_intel.tdx=1"
    ```

    3. Atualize o GRUB e reinicie:
    
    ```bash
    sudo update-grub
    sudo reboot
    ```

    4. Verifique se os parâmetros foram aplicados:
    ```bash
    cat /proc/cmdline
    # deve conter: nohibernate kvm_intel.tdx=1
    ```

    5. Confirme que o módulo TDX foi inicializado:
    ```bash
    sudo dmesg | grep -i tdx
    ```

    Saída esperada (exemplo): [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    ```text
    virt/tdx: BIOS enabled: private KeyID range 

    A linha `virt/tdx: module initialized` indica que TDX está ativo no host. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)



*  4. Instalar o stack de virtualização com suporte a TDX
Instale QEMU, OVMF com firmware TDX e libvirt. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

    ```bash
    sudo apt update
    sudo apt install \
      qemu-system-x86 \
      ovmf-inteltdx \
      libvirt-daemon-system \
      libvirt-clients
    ```

    - `qemu-system-x86`: QEMU com suporte a Intel TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - `ovmf-inteltdx`: firmware UEFI (OVMF) preparado para TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - `libvirt-daemon-system` e `libvirt-clients`: gerência de VMs via libvirt/virsh. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    
*  5.   Verifique se o firmware TDX‑capable está presente:
    ```bash
    ls -l /usr/share/ovmf/OVMF.inteltdx.ms.fd
    ```
    
    O arquivo deve existir e ter alguns MB. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    ## Usando o repositório canonical/tdx (atalho automatizado)
    A Canonical fornece um repositório Git com scripts para configurar o host TDX, criar imagem TD e subir a VM. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)

*  6. Clone o repositório no host Ubuntu 24.04:
    ```bash
    git clone -b noble-24.04 https://github.com/canonical/tdx.git
    cd tdx
    ```
    2. Opcionalmente ajuste o arquivo de configuração `setup-tdx-config` (por exemplo, se quiser que já instale componentes de atestação, defina `TDX_SETUP_ATTESTATION=1`). [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
*  7. Execute o script de setup de host:
    ```bash
    sudo ./setup-tdx-host.sh
    sudo reboot
    ```
    
    Esse script instala o stack TDX adequado, configura módulos, pacotes e ajustes adicionais para o host. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)


*  8. Depois do reboot, confirme novamente com:
    ```bash
    sudo dmesg | grep -i tdx
    ```

Você deve ver `virt/tdx: module initialized` indicando que o host está pronto. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
*  9. Criar imagem de guest (TD) baseada em Ubuntu
    Você pode usar duas abordagens principais: criar uma imagem TD nova ou converter uma VM existente. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
*  10. Criar nova imagem TD com scripts Canonical
    Num sistema Ubuntu (pode ser o próprio host):
    ```bash
    cd tdx/guest-tools/image
    sudo ./create-td-image.sh -v 24.04
    ```

    - Isso baixa uma cloud image do Ubuntu 24.04 e gera `tdx-guest-ubuntu-24.04-*.qcow2` com as customizações necessárias para rodar como TD. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    Valores padrão (por exemplo, senha root `123456`) devem ser trocados em ambiente de produção. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
*  11. Converter imagem de VM existente em TD
    Se você já tem uma VM Ubuntu 24.04/24.10:
    
    1. Suba a VM “normal”.  
    2. Baixe/clonar o repositório `canonical/tdx` dentro da VM. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    3. Rode:
    
    ```bash
    cd tdx
    sudo ./setup-tdx-guest.sh
    '```

    4. Desligue a VM: a imagem agora está preparada para TDX. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    ## Subir um TD usando QEMU diretamente
    Com o host já TDX‑enabled e a imagem de guest pronta, você pode iniciar uma TD com QEMU usando um comando similar ao da documentação Ubuntu: [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

    ```bash
    qemu-system-x86_64 \
      -accel kvm \
      -smp 32 \
      -m 16G \
      -cpu host \
      -object '{"qom-type":"tdx-guest","id":"tdx","quote-generation-socket":{"type":"vsock","cid":"2","port":"4050"}}' \
      -object memory-backend-ram,id=mem0,size=16G \
      -machine q35,kernel_irqchip=split,confidential-guest-support=tdx,memory-backend=mem0 \
      -bios /usr/share/ovmf/OVMF.inteltdx.ms.fd \
      -nographic \
      -nodefaults \
      -vga none \
      -drive file=tdx-guest-ubuntu-24.04-generic.qcow2,if=none,id=virtio-disk0 \
      -device virtio-blk-pci,drive=virtio-disk0 \
      -serial stdio
    ```

*  12.    Parâmetros TDX importantes: [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    
    - `-object "qom-type":"tdx-guest"...`: cria o objeto TDX guest e configura canal vsock para quotes/atestado. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - `-machine ... confidential-guest-support=tdx ...`: liga a máquina ao objeto TDX e usa memória protegida. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - `-object memory-backend-ram...`: define o backend de RAM que será criptografado pelo TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    - `-bios /usr/share/ovmf/OVMF.inteltdx.ms.fd`: firmware UEFI com suporte TDX e Secure Boot. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

*  13. Subir um TD via libvirt (virsh)
    A documentação do Ubuntu mostra um XML de domínio libvirt com `aunchSecurity type='tdx'>` e memória marcada como privada. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

    Exemplo simplificado (arquivo `tdx-vm.xml`): [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    
    ```xml
    <domain type='kvm' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
      <name>tdx-guest</name>
      <memory unit='GiB'>16</memory>
      <memoryBacking>
        <source type='anonymous'/>
        <access mode='private'/>
      </memoryBacking>
      <vcpu placement='static'>16</vcpu>
      <os>
        <type arch='x86_64' machine='q35'>hvm</type>
        oader type='rom' readonly='yes'>/usr/share/ovmf/OVMF.inteltdx.ms.fd</loader>
        <boot dev='hd'/>
      </os>
      pu mode='host-passthrough'>
        <topology sockets='1' cores='16' threads='1'/>
      </cpu>
      <devices>
        <emulator>/usr/bin/qemu-system-x86_64</emulator>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2'/>
          <source file='/var/lib/libvirt/images/tdx-guest-ubuntu-24.04-generic.qcow2'/>
          <target dev='vda' bus='virtio'/>
        </disk>
        sole type='pty'>
          <target type='virtio' port='1'/>
        </console>
      </devices>
      aunchSecurity type='tdx'>
        <policy>0x10000000</policy>
        <quoteGenerationService>
          <SocketAddress type='vsock' cid='2' port='4050'/>
        </quoteGenerationService>
      </launchSecurity>
    </domain>
    ```

*  14. Defina e inicie a VM:
    ```bash
    sudo virsh define tdx-vm.xml
    sudo virsh start tdx-guest
    sudo virsh console tdx-guest
    ```
    O campo `aunchSecurity type='tdx'>` e `memoryBacking` com `access mode="private"` são críticos para TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

*  14. Verificar TDX dentro do guest
Dentro da VM (TD) Ubuntu 24.04:

    ```bash
    sudo dmesg | grep -i tdx
    ```

    Saída esperada: [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)
    
    ```text
    tdx: Guest detected
    systemd [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/): Detected confidential virtualization tdx.
    ```
    
    Também verifique o dispositivo TDX guest:
    
    ```bash
    ls -l /dev/tdx_guest
    # deve existir como char device
    ```
    
    Esses sinais confirmam que o guest está rodando como Trust Domain TDX. [cc-enabling.trustedservices.intel](https://cc-enabling.trustedservices.intel.com/intel-tdx-enabling-guide/06/guest_os_setup/)

*  15.(Opcional) Atestação remota com Canonical/Intel
    Se você precisar de atestação (por exemplo, usar Intel Tiber Trust Services), o repositório `canonical/tdx` inclui scripts para instalar SGX DCAP no host e Trust Authority CLI no guest. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    Em alto nível: [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    - No host: `cd tdx/attestation && sudo ./setup-attestation-host.sh` para instalar SGX DCAP, QGS, PCCS e registrar a plataforma na Intel PCS. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    - No guest: `cd tdx/attestation && ./setup-attestation-guest.sh` para instalar `trustauthority-cli`, depois usar `trustauthority-cli quote` e `trustauthority-cli token -c config.json` com a API key do Intel Tiber Trust Service. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    Essas etapas são mais avançadas e necessárias apenas se você for usar atestação remota em produção. [intel](https://www.intel.fr/content/www/fr/fr/support/articles/000099762/processors/intel-xeon-processors.html)
    
    ***
    
    Você pretende usar TDX diretamente em bare metal local ou em cloud (por exemplo, Google Cloud/Outro CSP), para eu adaptar o passo‑a‑passo ao seu cenário específico?  
    
       
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

