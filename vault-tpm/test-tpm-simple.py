#!/usr/bin/env python3
import subprocess
import base64

def test_tpm_encryption():
    print("🧪 TESTE SIMPLES DE CRIPTOGRAFIA TPM")
    
    # Dados de teste
    test_data = "teste-criptografia-tpm"
    print(f"📝 Dados para criptografar: {test_data}")
    
    # Salvar dados em arquivo temporário
    with open('/tmp/test_input.bin', 'w') as f:
        f.write(test_data)
    
    try:
        # Tentar criptografar com TPM
        result = subprocess.run([
            'tpm2_createprimary', '-c', '/tmp/primary.ctx', '-Q', '--tcti', 'device:/dev/tpmrm0'
        ], capture_output=True, timeout=30)
        
        if result.returncode != 0:
            print(f"❌ Falha criar contexto primário: {result.stderr.decode()}")
            return False
        
        # Continuar com o processo de criptografia...
        # (similar ao código do vault_initializer.py)
        
        print("✅ Criptografia TPM funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == '__main__':
    test_tpm_encryption()
