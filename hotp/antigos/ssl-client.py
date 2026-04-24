import socket
import ssl
import os
from app1_client_otp import totp
import time
 
########
context = ssl.SSLContext(ssl.PROTOCOL_TLS)
context.options |= (
        ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
    )
 
context.verify_mode = ssl.CERT_REQUIRED
context.load_verify_locations('mycert.pem')
context.load_cert_chain(certfile='mycert.pem', keyfile='mykey.key')
 
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client = context.wrap_socket(client)
client.connect(("192.168.1.4", 4443))

mensagem = totp.now()
client.send(bytes('\nOTP code sent protected by TLS',encoding='utf8'))

# Enviando a mensagem para o Servidor TCP através da conexão
while mensagem != '\x18':
    mensagem = totp.now()
    client.send(str(mensagem).encode())
    print('\nOTP code sent: ', mensagem)
    time.sleep(1)

from_server = str(client.recv(4096),encoding='utf8')
print(from_server)
 
client.close()
