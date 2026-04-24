
# PROJETO HOTP - AUTENTICAÇÃO DE DOIS FATORES PARA SISTEMAS

# Dependências
    sudo apt install build-essential python3-dev libffi-dev libssl-dev
    
    pip install --upgrade pip setuptools wheel

    pip install fastapi uvicorn pyotp requests

# Servidor
    python server.py

    O terminal mostrará que o servidor está rodando em http://0.0.0.0:5000.

    No console do servidor, aparecerá uma linha escrita DEBUG: Secret para o cliente: XXXXX.... Copie esse código, pois você precisará dele para o script do cliente.

# Cliente
    Abra o arquivo client.py e ajuste a variável OTP_SECRET pelo valor obtido no lado do servidor.

    python client.py

# Fluxo de Testes
    Para validar se a lógica de "derrubar a sessão" está funcionando, você pode fazer o seguinte:

    Sucesso: Deixe o cliente rodar. A cada 60 segundos, ele enviará o código correto e o servidor responderá com Sessão Ativa.

    Falha (Derrubar Sessão): No script do cliente, altere temporariamente a função para enviar um número fixo errado (ex: otp_code="000000").

    Resultado: O servidor identificará o erro, removerá o token da lista active_sessions e o cliente receberá um erro 401, encerrando a execução.
    Como o servidor está configurado em 0.0.0.0, ele aceitará conexões de outros dispositivos na mesma rede local através do IP da sua máquina na porta 5000.
