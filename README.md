# app-tpm

Esta é uma Aplicação Web em Contêiner com Segurança via TPM.

# Passo 1 
Habilite o TPM no VirtualBox, caso esteja utilizando virtualização

# Passo 2
Atualize o Sistema Operacional Linux
  sudo apt update && sudo apt upgrade -y

# Passo 3
Instale as dependencias do docker docker-ce, docker-ce-cli, containerd.io e docker-compose-plugin, de acordo com o recomendado.

# Passo 4
Instale os pacotes para o sistema interagir com o TPM do host:
  sudo apt install tpm2-tools tpm2-abrmd -y

# Passo 5 
Verifique se o Linux reconheceu corretamente o dispositivo vTPM passado pelo VirtualBox. 
O kernel do Linux expõe o TPM como um dispositivo de caractere no sistema de arquivos. 
Execute o seguinte comando:
  ls -l /dev/tpm*
