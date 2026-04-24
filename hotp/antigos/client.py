# -*- coding: utf-8 -*-

import socket
import ssl

HOST = '192.168.56.1'      # Endereco IP do Servidor
PORT = 5000             # Porta que o Servidor está


#habilitando SSL
if __name__ == "__main__":
    # Create a context, just like as for the server
    context = ssl.create_default_context()
    # Load the server's CA
    context.load_verify_locations("ssl/rootCA.pem")


# Criando a conexão
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
destino = (HOST, PORT)
tcp.connect(destino)

print('\nDigite suas mensagens')
print('Para sair use CTRL+X\n')

# Recebendo a mensagem do usuário final pelo teclado
mensagem = input()

# Enviando a mensagem para o Servidor TCP através da conexão
while mensagem != '\x18':
    tcp.send(str(mensagem).encode())
    mensagem = input()

# Fechando o Socket
tcp.close()
