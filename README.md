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

As implementações específicas de código que suportam esta arquitetura podem ser encontradas no repositório base:
[https://github.com/juarez1972/app-tpm](https://github.com/juarez1972/app-tpm)

### Pré-requisitos
* Sistema com suporte a TPM 2.0 (ou simulador `swtpm`).
* Docker e Docker Compose instalados.
* Bibliotecas `tss2` para interação com o hardware.

## 5. Arquitetura Lógica

1.  **Boot:** O sistema valida o estado do firmware via TPM.
2.  **Unseal:** O serviço de Segredos (Vault) solicita a chave de descriptografia ao TPM.
3.  **Auth:** O usuário/serviço autentica-se via Zero Trust + HOTP.
4.  **Transaction:** Os dados são trocados utilizando HMAC para garantir que não houve alteração no percurso.

## 6. Licença

Este projeto está licenciado sob a Licença MIT - consulte o arquivo [LICENSE](LICENSE) para detalhes.

---
**Desenvolvido pelos pesquisdores da PUC-PR
** [Juarez de Oliveira] juarez.oliveira@pucpr.edu.br
** [Juliano Sartori Langaro] juliano.langaro@pucpr.edu.br
** [Fellipe M. Veiga] fellipe.veiga@pucpr.edu.br
sob a orientação do Prof. Doutor Altair Olivo Santin altair.santin@pucpr.br

