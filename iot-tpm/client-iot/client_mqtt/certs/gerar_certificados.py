import os
from datetime import datetime, timedelta, timezone
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def gerar_chave_privada():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

def salvar_pem(obj, filename, is_key=False):
    if is_key:
        encryption = serialization.NoEncryption()
        data = obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        )
    else:
        data = obj.public_bytes(serialization.Encoding.PEM)
    
    with open(filename, "wb") as f:
        f.write(data)

def criar_certificados():
    cert_dir = "./certs"
    os.makedirs(cert_dir, exist_ok=True)

    # Obter o tempo atual ciente do fuso horário (UTC) para evitar os Warnings
    agora = datetime.now(timezone.utc)

    print("[*] Gerando Autoridade Certificadora (CA)...")
    ca_key = gerar_chave_privada()
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"IoT Project CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Seguranca IoT"),
    ])
    ca_cert = x509.CertificateBuilder().subject_name(
        ca_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        ca_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        agora
    ).not_valid_after(
        agora + timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).sign(ca_key, hashes.SHA256())

    salvar_pem(ca_key, f"{cert_dir}/ca.key", is_key=True)
    salvar_pem(ca_cert, f"{cert_dir}/ca.crt")

    print("[*] Gerando Certificado do Servidor...")
    server_key = gerar_chave_privada()
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"host.docker.internal"),
    ])
    
    server_cert = x509.CertificateBuilder().subject_name(
        server_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        server_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        agora
    ).not_valid_after(
        agora + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u"host.docker.internal"),
            x509.DNSName(u"localhost"),
            # Correção aqui: convertendo a string para um objeto IPv4Address válido
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))
        ]),
        critical=False,
    ).sign(ca_key, hashes.SHA256())

    salvar_pem(server_key, f"{cert_dir}/server.key", is_key=True)
    salvar_pem(server_cert, f"{cert_dir}/server.crt")

    print(f"\n[+] Sucesso! Certificados gerados em: {os.path.abspath(cert_dir)}")
    print("Arquivos prontos: ca.crt, server.crt, server.key")

if __name__ == "__main__":
    criar_certificados()
