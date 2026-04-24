import pyotp
hotp = pyotp.HOTP('JBSWY3DPEHPK3PXP')
print(hotp.at(1)) # Gera o código para o contador 1
