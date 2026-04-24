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

base32secret = 'UOVSHEO5LROFRXDPPPWDPMOEYKLSKVNZ'
#print('Secret:', base32secret)
totp = pyotp.TOTP(base32secret)
#print('Código OTP:', totp.now())
# time.sleep(30)
# print('OTP code:', totp.now())

mfa_digitado = input('Please, input your personal OTP code:')
codigo_otp = totp.now()
print('OTP code sent:', mfa_digitado)
print('OTP code system:', codigo_otp)
def funcao_otp():
  if mfa_digitado != codigo_otp:
    print('The OTP Code is wrong. You will be desconnected. Bye bye!')
    time.sleep(30)    
  else:
    print('The OTP Code is correct! Welcome to this host!')
    time.sleep(2)
    os.system('bash')
funcao_otp()

