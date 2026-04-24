# -*- coding: utf-8 -*-

import socket
import ssl

HOST = '192.168.56.1'      # Endereco IP do Servidor

PORT = 5000         # Porta que o Servidor está

#Instalando SSL
if __name__ == "__main__":
    # First, create a context. The default settings are probably the best here.
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # Load the CA (self-signed, in this case) and the corresponding private key (also self-signed, in this case)
    context.load_cert_chain(certfile="ssl/rootCA.pem",
        keyfile="ssl/rootCA.key")

#Configurações do servidor

tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
origem = (HOST, PORT)

# Colocando um endereço IP e uma porta no Socket
tcp.bind(origem)

# Colocando o Socket em modo passivo
tcp.listen(1)

print('\nServidor TCP iniciado no IP', HOST, 'na porta', PORT)

while True:
    # Aceitando uma nova conexão
    conexao, cliente = tcp.accept()
    print('\nConexão realizada por:', cliente)

    while True:
        # Recebendo as mensagens através da conexão
        mensagem = conexao.recv(1024)
        if not mensagem:
            break

        # Exibindo a mensagem recebida
        print('\nCliente..:', cliente)
        print('Mensagem.:', mensagem.decode())

    print('Finalizando conexão do cliente', cliente)

    # Fechando a conexão com o Socket
    conexao.close()
