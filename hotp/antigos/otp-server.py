# -*- coding: utf-8 -*-

import socket
import pyotp
import time
from app1_client_otp import totp

HOST = '0.0.0.0'      # Endereco IP do Servidor

PORT = 5000         # Porta que o Servidor está

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
        print('O código recebido foi: ', mensagem.decode())

        # Comparando a mensagem recebida com o TOTP
        #while True:
        #    mensagem.decode() == totp.now()

    print('Finalizando conexão do cliente', cliente)

    # Fechando a conexão com o Socket
    conexao.close()
