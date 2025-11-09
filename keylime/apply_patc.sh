#!/bin/bash

echo "=== APLICANDO PATCH NO KEYLIME ==="

cd keylime_server_setup

# Parar serviços
sudo docker-compose down

# Criar script de patch
cat > patch_keylime.py << 'EOF'
#!/usr/bin/env python3
import os
import sys

def patch_keylime_db():
    # Encontrar o arquivo keylime_db.py
    for path in sys.path:
        db_path = os.path.join(path, 'keylime', 'db', 'keylime_db.py')
        if os.path.exists(db_path):
            print(f"Encontrado: {db_path}")
            
            # Ler o conteúdo
            with open(db_path, 'r') as f:
                content = f.read()
            
            # Aplicar o patch
            old_code = '''    p_sz, m_ovfl = p_sz_m_ovfl.split(",")'''
            new_code = '''    # PATCH: Corrigir erro de split do pool_size
    if p_sz_m_ovfl and "," in p_sz_m_ovfl:
        p_sz, m_ovfl = p_sz_m_ovfl.split(",")
    else:
        # Valores padrão se não houver vírgula
        p_sz = p_sz_m_ovfl if p_sz_m_ovfl else "5"
        m_ovfl = "10"'''
            
            if old_code in content:
                content = content.replace(old_code, new_code)
                with open(db_path, 'w') as f:
                    f.write(content)
                print("✅ Patch aplicado com sucesso!")
                return True
            else:
                print("❌ Código original não encontrado para aplicar o patch")
                return False
    
    print("❌ Não foi possível encontrar keylime/db/keylime_db.py")
    return False

if __name__ == "__main__":
    patch_keylime_db()
EOF

# Aplicar o patch durante o build
cat >> Dockerfile << 'EOF'

# Aplicar patch para corrigir pool_size
COPY patch_keylime.py /tmp/patch_keylime.py
RUN python3 /tmp/patch_keylime.py && rm /tmp/patch_keylime.py
EOF

echo "✅ Dockerfile atualizado com patch"

# Reconstruir
sudo docker-compose build --no-cache
sudo docker-compose up -d

echo "Aguardando inicialização..."
sleep 20

echo "=== STATUS ==="
sudo docker ps

echo "=== LOGS DO REGISTRAR ==="
sudo docker logs keylime-registrar --tail=15

if curl -s http://localhost:8890/v1/status >/dev/null; then
    echo "🎉 ✅ REGISTRAR FUNCIONANDO!"
else
    echo "❌ Ainda com problemas, tentando abordagem alternativa..."
    
    # Abordagem alternativa: usar versão mais antiga e estável
    echo "Tentando com versão 7.4.0..."
    cat > Dockerfile.fallback << 'EOF'
FROM fedora:38

# Instalar dependências do sistema
RUN dnf update -y && \
    dnf install -y python3-pip python3-devel git gcc openssl-devel openssl python3-gpg sqlite && \
    dnf clean all

# Criar diretórios necessários
RUN mkdir -p /var/lib/keylime /etc/keylime

# Copiar requirements
COPY requirements.txt /tmp/requirements.txt

# Instalar dependências Python
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Instalar Keylime versão 7.4.0 (mais estável)
RUN pip3 install keylime==7.4.0

WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python3 -c "import keylime; print('OK')" || exit 1
EOF
    
    sudo docker-compose down
    cp Dockerfile.fallback Dockerfile
    sudo docker-compose build --no-cache
    sudo docker-compose up -d
    
    sleep 20
    sudo docker logs keylime-registrar --tail=15
fi
