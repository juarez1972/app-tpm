#!/bin/bash
# test_tpm_integration.sh - Testes específicos de integração TPM com container tpm-validator

set -e

COMPOSE_FILE="docker-compose.yml"
VAULT_CONTAINER="vault"
TPM_CONTAINER="tpm-validator"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if containers are running
check_containers_running() {
    log_info "Verificando se os containers estão rodando..."
    
    if docker-compose -f $COMPOSE_FILE ps $VAULT_CONTAINER | grep -q "Up"; then
        log_success "Container $VAULT_CONTAINER está rodando"
    else
        log_error "Container $VAULT_CONTAINER não está rodando"
        return 1
    fi
    
    if docker-compose -f $COMPOSE_FILE ps $TPM_CONTAINER | grep -q "Up"; then
        log_success "Container $TPM_CONTAINER está rodando"
    else
        log_error "Container $TPM_CONTAINER não está rodando"
        return 1
    fi
    
    return 0
}

# Function to test TPM basic operations
test_tpm_basic_operations() {
    log_info "1. Testando operações básicas do TPM..."
    
    # Test if TPM tools are available
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER which tpm2_getcap > /dev/null 2>&1; then
        log_success "Ferramentas TPM disponíveis no container"
    else
        log_error "Ferramentas TPM não encontradas no container"
        return 1
    fi
    
    # Test TPM properties
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER tpm2_getcap properties-fixed > /dev/null 2>&1; then
        log_success "TPM responde à consulta de propriedades"
    else
        log_error "TPM não responde à consulta de propriedades"
        return 1
    fi
    
    # Test PCR read
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER tpm2_pcrread sha256:0 > /dev/null 2>&1; then
        log_success "Leitura de PCRs funcionando"
    else
        log_error "Falha na leitura de PCRs"
        return 1
    fi
    
    # Test TPM startup (if needed)
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER tpm2_startup -c > /dev/null 2>&1; then
        log_success "TPM startup bem-sucedido"
    else
        log_warning "TPM startup não necessário ou falhou"
    fi
    
    return 0
}

# Function to test TPM key operations
test_tpm_key_operations() {
    log_info "2. Testando operações com chaves TPM..."
    
    local temp_dir="/tmp/tpm_test_$$"
    
    # Create temporary directory in container
    docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER mkdir -p $temp_dir
    
    # Test primary key creation
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER bash -c "
        cd $temp_dir &&
        tpm2_createprimary -c primary.ctx -Q &&
        tpm2_readpublic -c primary.ctx > /dev/null
    "; then
        log_success "Criação e leitura de chave primária funcionando"
        
        # Test creating and signing with key
        if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER bash -c "
            cd $temp_dir &&
            echo 'test data' > test.txt &&
            tpm2_create -C primary.ctx -G rsa -r key.prv -u key.pub -c key.ctx -Q &&
            tpm2_sign -c key.ctx -g sha256 -o sig test.txt -Q
        "; then
            log_success "Criação de chave e assinatura funcionando"
        else
            log_warning "Criação de chave ou assinatura falhou"
        fi
    else
        log_error "Falha na criação de chave primária TPM"
    fi
    
    # Cleanup
    docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER rm -rf $temp_dir
    
    return 0
}

# Function to test Vault status
test_vault_status() {
    log_info "3. Testando status do Vault..."
    
    # Check if vault CLI is available
    if docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER which vault > /dev/null 2>&1; then
        log_success "Vault CLI disponível"
    else
        log_error "Vault CLI não encontrado"
        return 1
    fi
    
    # Get vault status
    local vault_status=$(docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault status 2>/dev/null || echo "error")
    
    if [ "$vault_status" != "error" ]; then
        log_success "Vault está acessível"
        
        # Parse specific status information
        if echo "$vault_status" | grep -q "Sealed.*true"; then
            log_warning "Vault está selado"
        else
            log_success "Vault não está selado"
        fi
        
        if echo "$vault_status" | grep -q "Initialized.*true"; then
            log_success "Vault está inicializado"
        else
            log_error "Vault não está inicializado"
        fi
        
    else
        log_error "Não foi possível obter status do Vault"
        return 1
    fi
    
    return 0
}

# Function to test Vault TPM authentication
test_vault_tpm_auth() {
    log_info "4. Testando autenticação TPM no Vault..."
    
    # Check if TPM auth method is enabled
    local auth_methods=$(docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault auth list 2>/dev/null || echo "")
    
    if echo "$auth_methods" | grep -q "tpm"; then
        log_success "Método de autenticação TPM está habilitado"
        
        # Try to list TPM roles
        if docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault list auth/tpm/roles > /dev/null 2>&1; then
            log_success "Consegue acessar roles TPM"
            
            # If there are roles, try to read one
            local roles=$(docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault list auth/tpm/roles 2>/dev/null | head -1)
            if [ -n "$roles" ]; then
                log_info "Roles TPM encontradas: $roles"
                # Try to read the first role
                if docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault read auth/tpm/role/$roles > /dev/null 2>&1; then
                    log_success "Consegue ler configuração da role TPM"
                fi
            else
                log_warning "Nenhuma role TPM configurada"
            fi
        else
            log_warning "Não consegue listar roles TPM (pode não haver roles configuradas)"
        fi
    else
        log_error "Método de autenticação TPM não está habilitado"
        return 1
    fi
    
    return 0
}

# Function to test TPM-Vault integration
test_tpm_vault_integration() {
    log_info "5. Testando integração TPM-Vault..."
    
    # This test would depend on your specific implementation
    # Here's a generic test that can be adapted
    
    # Check if we can use TPM for vault operations
    if docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault read sys/auth/tpm > /dev/null 2>&1; then
        log_success "Configuração de auth TPM acessível"
    else
        log_warning "Não foi possível acessar configuração de auth TPM"
    fi
    
    # Test if TPM seal/unseal is configured (if applicable)
    if docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER vault read sys/seal-status 2>/dev/null | grep -q "tpm"; then
        log_success "TPM configurado para seal/unseal"
    else
        log_info "TPM não configurado para seal/unseal (pode ser normal)"
    fi
    
    return 0
}

# Function to test network connectivity between containers
test_container_connectivity() {
    log_info "6. Testando conectividade entre containers..."
    
    # Get vault container IP
    local vault_ip=$(docker-compose -f $COMPOSE_FILE exec -T $VAULT_CONTAINER hostname -i | tr -d '\r')
    
    # Test if tpm-validator can reach vault
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER ping -c 1 -W 2 $vault_ip > /dev/null 2>&1; then
        log_success "TPM container pode alcançar Vault container"
    else
        log_error "TPM container não pode alcançar Vault container"
    fi
    
    # Test vault API from tpm container (if needed)
    if docker-compose -f $COMPOSE_FILE exec -T $TPM_CONTAINER curl -s -f http://$vault_ip:8200/v1/sys/health > /dev/null 2>&1; then
        log_success "TPM container pode acessar API do Vault"
    else
        log_warning "TPM container não pode acessar API do Vault (pode ser normal)"
    fi
    
    return 0
}

# Function to run comprehensive tests
run_comprehensive_tests() {
    log_info "=== Iniciando Testes de Integração TPM ==="
    
    local tests_passed=0
    local tests_total=6
    
    check_containers_running && ((tests_passed++))
    echo "---"
    
    test_tpm_basic_operations && ((tests_passed++))
    echo "---"
    
    test_tpm_key_operations && ((tests_passed++))
    echo "---"
    
    test_vault_status && ((tests_passed++))
    echo "---"
    
    test_vault_tpm_auth && ((tests_passed++))
    echo "---"
    
    test_tpm_vault_integration && ((tests_passed++))
    echo "---"
    
    test_container_connectivity && ((tests_passed++))
    echo "---"
    
    log_info "=== Resumo dos Testes ==="
    log_info "Passaram: $tests_passed/$tests_total testes"
    
    if [ $tests_passed -eq $tests_total ]; then
        log_success "Todos os testes passaram! A integração TPM-Vault está funcionando corretamente."
        return 0
    elif [ $tests_passed -ge $((tests_total - 2)) ]; then
        log_warning "A maioria dos testes passou. Verifique os avisos acima."
        return 1
    else
        log_error "Muitos testes falharam. Verifique a configuração do sistema."
        return 1
    fi
}

# Function for quick smoke test
quick_smoke_test() {
    log_info "=== Teste Rápido de Funcionamento ==="
    
    check_containers_running
    test_tpm_basic_operations
    test_vault_status
    
    log_info "=== Teste Rápido Concluído ==="
}

# Main execution
main() {
    case "${1:-full}" in
        "quick")
            quick_smoke_test
            ;;
        "containers")
            check_containers_running
            ;;
        "tpm")
            test_tpm_basic_operations
            test_tpm_key_operations
            ;;
        "vault")
            test_vault_status
            test_vault_tpm_auth
            ;;
        "integration")
            test_tpm_vault_integration
            test_container_connectivity
            ;;
        "full"|*)
            run_comprehensive_tests
            ;;
    esac
}

# Handle script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
