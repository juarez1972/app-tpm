import hvac
import sys
#import json
#import requests

client = hvac.Client(url='http://192.168.153.200:8200')
print(f" Is client authenticated: {client.is_authenticated()}")

# Reading a secret
result = client.secrets.kv.v2.read_secret_version(mount_point='kv2', path='app-otp')

#print('Value under path "kv2/app-otp" / key "totp": {val}'.format(val=result['data']['data']['totp']))
print('{val}'.format(val=result['data']['data']['totp']))
chave = ('{val}'.format(val=result['data']['data']['totp']))
print(chave)


