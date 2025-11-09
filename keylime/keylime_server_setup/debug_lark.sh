#!/bin/bash

echo "🔍 DIAGNÓSTICO COMPLETO DO LARK"

cd keylime_server_setup

# Verificar requirements.txt
echo "=== REQUIREMENTS.TXT ==="
cat requirements.txt | grep -i lark

# Verificar pip list
echo "=== PIP LIST ==="
docker run --rm keylime_server_setup_keylime-registrar pip3 list | grep -i lark

# Verificar se pode importar
echo "=== IMPORT TEST ==="
docker run --rm keylime_server_setup_keylime-registrar python3 -c "
import sys
print('Python version:', sys.version)

print('Trying to find lark...')
try:
    import lark
    print('✅ SUCCESS: Lark imported')
    print('Version:', lark.__version__)
    print('File:', lark.__file__)
except ImportError:
    print('❌ FAILED: Lark not found')
    print('Searching in sys.path...')
    for path in sys.path:
        print(f'  {path}')
    
    print('Trying to install lark...')
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'lark'])
    
    try:
        import lark
        print('✅ Lark installed successfully!')
    except ImportError as e:
        print(f'❌ Still failed: {e}')
"

echo "=== DOCKERFILE CHECK ==="
cat Dockerfile | grep -i lark

echo "=== BUILD LOGS ==="
docker-compose build --no-cache | tail -20
