#  app-tpm - Esta é uma Aplicação Web em Contêiner com Segurança via TPM.

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

# Passo 56
Para validar a arquitetura completa, siga este procedimento passo a passo dentro do terminal da sua VM Linux, dentro da pasta com todos os arquivos baixados do git.
# Preparar o Segredo Lacrado: 
  chmod +x setup_secret.sh
  ./setup_secret.sh
# Construir e Iniciar a Aplicação com Docker Compose: 
  docker compose up --build
# Observar o Sucesso da Autenticação:
Analise os logs de saída no terminal. Você deverá ver as mensagens de log da aplicação app.py, indicando uma sequência de sucesso:
# Acessar a Aplicação:
Acesse http://<IP_DA_VM>:8000. 
Você deverá ver a mensagem: "Hello, World! A aplicação está rodando após a verificação bem-sucedida do TPM."
# Demonstrar o Cenário de Falha:
Para provar que o portão de segurança está funcionando, simule um cenário onde o contêiner não tem acesso ao TPM.
Pressione Ctrl+C no terminal para parar a aplicação.
Edite o arquivo docker-compose.yml e comente ou remova a seção devices.
Execute novamente o comando para iniciar a aplicação:
  docker compose up --build
Observe os logs de saída. Desta vez, a aplicação deve falhar. Você verá mensagens de erro como:
    FALHA NA AUTENTICAÇÃO DO TPM: Não foi possível deslacrar o segredo.
    Stderr: ERROR:tcti:src/tss2-tcti/tcti-device.c:452:Tss2_Tcti_Device_Init() Failed to open device file /dev/tpm0: No such file or directory
    A verificação do TPM falhou. A aplicação será encerrada.
O contêiner será encerrado com um código de erro, demonstrando que a autenticação via TPM é um pré-requisito obrigatório para a execução.

# Avançando a Arquitetura: Rumo à Atestação Pronta para Produção:
Agora vamos testar a arquitetura utilizando o Keylime

