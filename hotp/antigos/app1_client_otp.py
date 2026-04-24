# -*- coding: utf-8 -*-

#pip install pyotp cryptography base256
import time
import pyotp
##

"""Gerar TOTP - Lado do cliente
"""
base32secret = 'UOVSHEO5LROFRXDPPPWDPMOEYKLSKVNZ'
print('\nSecret:', base32secret)
totp = pyotp.TOTP(base32secret)
print('OTP code:', totp.now())
#time.sleep(30)

