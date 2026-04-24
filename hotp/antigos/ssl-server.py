import socket
import ssl
from app1_client_otp import totp
import time

 
#pemServer = "ssl/rootCA.pem"
#keyClient = "ssl/device.key"
#pemClient = "ssl/device.crt"
 
context = ssl.SSLContext(ssl.PROTOCOL_TLS)
context.options |= (
        ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
    )
 
context.verify_mode = ssl.CERT_REQUIRED
context.load_verify_locations('ssl/mycert.pem')
context.load_cert_chain(certfile='ssl/mycert.pem', keyfile='ssl/mykey.key')
 
serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 
serv = context.wrap_socket(serv)
 
serv.bind(("192.168.1.4", 4443))
serv.listen(5)
 
while True:
    conn, addr = serv.accept()
    from_client = ''
    
    while True:
        data = str(conn.recv(4096), encoding='utf8') # The received data type is byte, converted to str
        mensagem = conn.recv(1024)
        if not data:
            break
        from_client = from_client + data
         
        print('\nOTP code received: ', data, '\n')

        # Comparando a mensagem recebida com o TOTP
        # while True:
        #    mensagem.decode() == totp.now()
        #    time.sleep(30)
        #    print('\nA mensagem recebida bate com o TOTP')

        #conn.send(bytes("O servidor recebeu sua mensagem, fique tranquilo:\n",encoding='utf8')) 
 
    conn.close()
