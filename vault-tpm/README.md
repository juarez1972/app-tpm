# Hashicorp Vault em container validado por TPM
    Esta aplicação foi desenvolvida para proteger um cofre de senhas Hashicorp Vault, que só iniciará após a validação pela TPM do host. 
    Possui ainda uma aplicação web que funciona na porta 5000 com o mesmo objetivo. 
    O Vault funciona na porta 8200 (a criptografia deve ser adicionada antes de ser colocado em produção)
    
    Boot → TPM Validation → Vault Unseal → Sistema Operacional
        ✅           ✅           ✅             ✅

# Estrutura de Arquivos

                ─   app.py
                ├── backup_20251110_003314
                │   └── tpm-data
                │       ├── secret
                │       └── vault-root-key
                ├── docker-compose-fixed.yml
                ├── docker-compose.yml
                ├── Dockerfile
                ├── README.md
                ├── requirements.txt
                ├── scripts
                │   └── setup_vault_policies.hcl
                ├── setup_secret.sh
                ├── system_status.sh
                ├── templates
                │   └── index.html
                ├── tpm-data
                │   ├── secret
                │   └── vault-root-key
                ├── validade_system.sh
                ├── vault-config.hcl
                ├── vault-data
                └── vault-init
                    ├── Dockerfile
                    ├── requirements.txt
                    └── vault_initializer.py

    ✅ COMPONENTES OPERACIONAIS:
        🔐 TPM Validator: Valida integridade do hardware via TPM
        🗄️ HashiCorp Vault: Armazena secrets de forma segura
        🔄 Vault Initializer: Orquestra sequência segura de inicialização
        💾 Persistência: Dados mantidos entre reinicializações
    
    ✅ TESTES REALIZADOS E APROVADOS:
        ✅ Validação TPM em tempo real
        ✅ Comunicação entre containers
        ✅ Escrita/leitura no Vault
        ✅ Persistência de dados
        ✅ Recuperação automática
        ✅ Health checks contínuos
        
    🎯 BENEFÍCIOS CONQUISTADOS
    
    🔒 Segurança:
        Hardware Root of Trust via TPM
        Cadeia de Confiança estabelecida
        Vault só opera em máquina validada
        Secrets protegidos por hardware criptográfico

    ⚡ Operacional:
        Inicialização automática e segura
        Persistência de dados garantida
        Monitoramento integrado
        Escalabilidade preparada

    🏢 Enterprise Ready:
        Arquitetura de nível corporativo
        Logs auditáveis
        Health checks automatizados
        Documentação completa

    📞 SUPORTE E MANUTENÇÃO
        Verificações Regulares:
    
        Status do TPM: curl http://localhost:5000/status
        Health do Vault: curl http://localhost:8200/v1/sys/health
        Logs do Sistema: docker-compose logs --tail=20

    ⚡ Scripts de testes:
        system_status.sh e validade_system.sh

    
