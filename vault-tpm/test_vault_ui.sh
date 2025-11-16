#!/bin/bash
echo "=== VERIFICAÇÃO DA UI DO VAULT ==="

TOKEN="temp-root-token"

echo "1. Verificando se a UI está respondendo..."
curl -s http://localhost:8200/ui/ > /dev/null && echo "✅ UI está respondendo" || echo "❌ UI não responde"

echo -e "\n2. Listando secrets disponíveis para testar na UI:"
curl -s -H "X-Vault-Token: $TOKEN" \
  http://localhost:8200/v1/secret/metadata/?list=true | jq -r '.data.keys[]' 2>/dev/null | while read secret; do
  echo "   📁 $secret"
done

echo -e "\n3. Testando leitura de um secret via API:"
curl -s -H "X-Vault-Token: $TOKEN" \
  http://localhost:8200/v1/secret/data/app/database | jq '.data.data' 2>/dev/null && echo "✅ Secrets estão acessíveis" || echo "❌ Erro ao acessar secrets"

echo -e "\n4. Informações de acesso:"
echo "   🌐 URL: http://localhost:8200"
echo "   🔑 Token: $TOKEN"
echo "   📝 Dica: Use o menu 'Secrets' → 'secret' para ver os dados"

echo -e "\n=== INSTRUÇÕES ==="
echo "1. Abra http://localhost:8200 no navegador"
echo "2. Cole o token: temp-root-token"
echo "3. Explore o dashboard e os secrets"
echo "4. Tente criar um novo secret manualmente"
