# -*- coding: utf-8 -*-

import socket
from app1_client_otp import totp
import time

HOST = '192.168.56.1'      # Endereco IP do Servidor
PORT = 5000             # Porta que o Servidor está

# Criando a conexão
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
destino = (HOST, PORT)
tcp.connect(destino)

#print('\nDigite seu otp')
#print('Para sair use CTRL+X\n')

# Recebendo a mensagem do usuário final pelo teclado
mensagem = totp.now()

# Enviando a mensagem para o Servidor TCP através da conexão
while mensagem != '\x18':
    tcp.send(str(mensagem).encode())
    
    # Recebendo a mensagem do usuário final pelo teclado
    mensagem = totp.now()
    print('O código enviado foi: ', mensagem)
    time.sleep(1)

# Fechando o Socket
tcp.close()
