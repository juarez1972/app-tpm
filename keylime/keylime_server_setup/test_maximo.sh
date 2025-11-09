#!/bin/bash
echo "🧪 TESTE MÁXIMO KEYLIME - VERIFICAÇÃO TOTAL"

docker run --rm keylime_server_setup_keylime-registrar python3 -c "
import sys
print(f'🐍 Python: {sys.version}')

# Lista MÁXIMA de dependências
max_deps = [
    ('packaging', 'packaging'),
    ('cryptography', 'cryptography'),
    ('tornado', 'tornado'),
    ('sqlalchemy', 'sqlalchemy'),
    ('requests', 'requests'),
    ('yaml', 'yaml'),
    ('pycryptodome', 'Crypto'),
    ('alembic', 'alembic'),
    ('pyasn1', 'pyasn1'),
    ('pyasn1-modules', 'pyasn1_modules'),
    ('jsonschema', 'jsonschema'),
    ('gnupg', 'gnupg'),
    ('psutil', 'psutil'),
    ('importlib-metadata', 'importlib.metadata'),
    ('click', 'click'),
    ('asn1crypto', 'asn1crypto'),
    ('configparser', 'configparser'),
    ('flask', 'flask'),
    ('werkzeug', 'werkzeug'),
    ('jinja2', 'jinja2'),
    ('markupsafe', 'markupsafe'),
    ('itsdangerous', 'itsdangerous')
]

print('\\n📦 VERIFICAÇÃO MÁXIMA:')
perfect = True
for name, module in max_deps:
    try:
        if module == 'importlib.metadata':
            import importlib.metadata
        elif module == 'pyasn1_modules':
            import pyasn1_modules
        else:
            __import__(module)
        print(f'✅ {name}')
    except ImportError as e:
        print(f'❌ {name}: {e}')
        perfect = False

if not perfect:
    print('\\n💥 ALGUMAS DEPENDÊNCIAS FALTANDO!')
    exit(1)

print('\\n🔧 TESTE KEYLIME MÁXIMO...')
try:
    # Testar absolutamente TUDO
    import keylime
    print(f'✅ Keylime v{keylime.__version__}')
    
    # Módulos core
    from keylime import config, keylime_logging, api_version
    print('✅ Módulos core')
    
    # Comandos
    from keylime.cmd import registrar, verifier, agent
    print('✅ Comandos')
    
    # Common
    from keylime.common import migrations
    print('✅ Common')
    
    # Models
    from keylime.models import da_manager, db_manager
    from keylime.models.base import types
    from keylime.models.base.types import certificate
    print('✅ Models')
    
    # TPM
    from keylime.tpm import tpm_main
    print('✅ TPM')
    
    # Agent states
    from keylime.agentstates import AgentAttestState
    print('✅ Agent states')
    
    # IMA
    from keylime.ima.file_signatures import ImaKeyrings
    print('✅ IMA')
    
    print('\\n🎉🎉🎉 KEYLIME COMPLETAMENTE OPERACIONAL! 🎉🎉🎉')
    
except Exception as e:
    print(f'💥 ERRO CRÍTICO: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"
