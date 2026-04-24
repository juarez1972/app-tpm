# -*- coding: utf-8 -*-

import os
import pyotp
import time
from cryptography.fernet import Fernet
import base64
##
import base256
from os import remove
from base256 import encode, decode, encode_hex, decode_hex, encode_file, decode_file, encode_string, decode_string
##
import hashlib
import warnings
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

base32secret = 'UOVSHEO5LROFRXDPPPWDPMOEYKLSKVNZ'
print('Secret:', base32secret)
totp = pyotp.TOTP(base32secret)
print('OTP code:', totp.now())
# time.sleep(30)
# print('OTP code:', totp.now())

mfa_digitado = input('Input OTP code:')
codigo_otp = totp.now()
print('Typed OTP code:', mfa_digitado)
print('Sytem OTP code:', codigo_otp)
def funcao_otp():
  if mfa_digitado != codigo_otp:
    print('Wrong OTP code! Desconnecting API or SSH client')
#   os.system("./derruba_ssh_remoto.sh")

  else:
    print('Running SGX app to manage OTP code. Right OTP code. Client can continue')
    os.system('cd /opt/projetos/SampleCode/SampleEnclave/; ./app')
funcao_otp()

