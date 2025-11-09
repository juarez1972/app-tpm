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
