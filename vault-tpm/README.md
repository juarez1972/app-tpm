# Hashicorp Vault em container validado por TPM
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

