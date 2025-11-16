#!/bin/bash

# system_status.sh - Script para verificar a infraestrutura TPM + Vault com Docker
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
VAULT_SERVICE="vault"
TPM_SERVICE="tpm-service"  # Adjust based on your compose file
NETWORK_NAME="vault-tpm-network"

# Logging functions
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

# Function to check command existence
check_command() {
    if command -v $1 &> /dev/null; then
        log_success "$1 encontrado"
        return 0
    else
        log_error "$1 não encontrado"
        return 1
    fi
}

# Function to check Docker and Docker Compose
check_docker() {
    log_info "Verificando Docker e Docker Compose..."
    
    check_command docker
    check_command docker-compose
    
    # Check Docker daemon
    if docker info &> /dev/null; then
        log_success "Docker daemon está rodando"
    else
        log_error "Docker daemon não está rodando"
        return 1
    fi
    
    # Check compose file
    if [ -f "$COMPOSE_FILE" ]; then
        log_success "Arquivo $COMPOSE_FILE encontrado"
    else
        log_error "Arquivo $COMPOSE_FILE não encontrado"
        return 1
    fi
}

# Function to check container status
check_containers() {
    log_info "Verificando status dos containers..."
    
    # Check if services are defined in compose file
    local services=$(docker-compose -f $COMPOSE_FILE config --services 2>/dev/null)
    
    if [ -z "$services" ]; then
        log_error "Não foi possível ler serviços do docker-compose"
        return 1
    fi
    
    log_info "Serviços encontrados: $services"
    
    # Check each service
    for service in $services; do
        local container_id=$(docker-compose -f $COMPOSE_FILE ps -q $service)
        
        if [ -z "$container_id" ]; then
            log_error "Container para serviço $service não encontrado"
            continue
        fi
        
        local status=$(docker inspect --format='{{.State.Status}}' $container_id 2>/dev/null)
        local health=$(docker inspect --format='{{.State.Health.Status}}' $container_id 2>/dev/null)
        local running=$(docker inspect --format='{{.State.Running}}' $container_id 2>/dev/null)
        
        if [ "$running" = "true" ]; then
            if [ "$health" = "healthy" ]; then
                log_success "Container $service está rodando e saudável"
            elif [ "$health" = "unhealthy" ]; then
                log_error "Container $service está rodando mas não saudável"
            else
                log_success "Container $service está rodando (health check não configurado)"
            fi
        else
            log_error "Container $service não está rodando (status: $status)"
        fi
    done
    
    return 0
}

# Function to check TPM availability
check_tpm() {
    log_info "Verificando disponibilidade do TPM..."
    
    # Check if TPM device exists on host
    if [ -c /dev/tpm0 ] || [ -c /dev/tpmrm0 ]; then
        log_success "Dispositivo TPM detectado no host"
    else
        log_warning "Dispositivo TPM não encontrado no host"
    fi
    
    # Check TPM in containers
    local tpm_services=$(docker-compose -f $COMPOSE_FILE config --services | grep -i tpm || echo "")
    
    for service in $tpm_services; do
        log_info "Verificando TPM no serviço $service..."
        
        # Try to execute TPM command in container
        if docker-compose -f $COMPOSE_FILE exec -T $service which tpm2_getcap &> /dev/null; then
            log_success "Ferramentas TPM disponíveis em $service"
            
            # Test basic TPM operation
            if docker-compose -f $COMPOSE_FILE exec -T $service tpm2_getcap properties-fixed &> /dev/null; then
                log_success "TPM operacional em $service"
            else
                log_error "TPM não responde em $service"
            fi
        else
            log_warning "Ferramentas TPM não encontradas em $service"
        fi
    done
    
    return 0
}

# Function to check Vault status
check_vault() {
    log_info "Verificando status do Vault..."
    
    # Find vault service
    local vault_service=$(docker-compose -f $COMPOSE_FILE config --services | grep -i vault | head -1)
    
    if [ -z "$vault_service" ]; then
        log_error "Serviço Vault não encontrado no docker-compose"
        return 1
    fi
    
    log_info "Usando serviço Vault: $vault_service"
    
    # Check if vault CLI is available in container
    if ! docker-compose -f $COMPOSE_FILE exec -T $vault_service which vault &> /dev/null; then
        log_error "Vault CLI não encontrado no container"
        return 1
    fi
    
    # Check Vault status
    local vault_status=$(docker-compose -f $COMPOSE_FILE exec -T $vault_service vault status 2>/dev/null)
    local vault_exit_code=$?
    
    if [ $vault_exit_code -eq 0 ]; then
        log_success "Vault está inicializado e acessível"
        
        # Parse vault status
        if echo "$vault_status" | grep -q "Sealed.*true"; then
            log_warning "Vault está selado"
        else
            log_success "Vault não está selado"
        fi
        
        if echo "$vault_status" | grep -q "HA Enabled.*true"; then
            log_success "HA está habilitado"
        fi
        
    elif [ $vault_exit_code -eq 2 ]; then
        log_error "Vault não está inicializado"
    else
        log_error "Não foi possível conectar ao Vault"
    fi
    
    return $vault_exit_code
}

# Function to check Vault TPM auth
check_vault_tpm_auth() {
    log_info "Verificando autenticação TPM no Vault..."
    
    local vault_service=$(docker-compose -f $COMPOSE_FILE config --services | grep -i vault | head -1)
    
    # Check if TPM auth method is enabled
    local auth_methods=$(docker-compose -f $COMPOSE_FILE exec -T $vault_service vault auth list 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        if echo "$auth_methods" | grep -q "tpm"; then
            log_success "Método de autenticação TPM está habilitado"
        else
            log_warning "Método de autenticação TPM não está habilitado"
        fi
    else
        log_error "Não foi possível listar métodos de autenticação"
    fi
    
    return 0
}

# Function to check network connectivity
check_network() {
    log_info "Verificando conectividade de rede..."
    
    # Check Docker network
    local network_exists=$(docker network ls --filter name=$NETWORK_NAME --format "{{.Name}}")
    
    if [ "$network_exists" = "$NETWORK_NAME" ]; then
        log_success "Rede Docker '$NETWORK_NAME' encontrada"
    else
        log_warning "Rede Docker '$NETWORK_NAME' não encontrada"
    fi
    
    # Check Vault API
    local vault_port=$(docker-compose -f $COMPOSE_FILE port vault 8200 2>/dev/null | cut -d: -f2)
    
    if [ -n "$vault_port" ]; then
        if curl -s -f "http://127.0.0.1:$vault_port/v1/sys/health" &> /dev/null; then
            log_success "Vault API está respondendo na porta $vault_port"
        else
            log_error "Vault API não está respondendo na porta $vault_port"
        fi
    else
        log_warning "Porta do Vault não mapeada para o host"
    fi
    
    return 0
}

# Function to check resources
check_resources() {
    log_info "Verificando recursos do sistema..."
    
    # Memory
    local mem_free=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    if [ "$mem_free" -gt 1048576 ]; then
        log_success "Memória disponível: $(($mem_free/1024)) MB"
    else
        log_warning "Memória disponível baixa: $(($mem_free/1024)) MB"
    fi
    
    # CPU
    local load=$(cat /proc/loadavg | awk '{print $1}')
    local cores=$(nproc)
    if (( $(echo "$load < $cores" | bc -l 2>/dev/null || echo "1") )); then
        log_success "Load average: $load"
    else
        log_warning "Load average alto: $load"
    fi
    
    # Docker disk usage
    local docker_disk=$(docker system df --format "{{.Size}}" 2>/dev/null | head -1)
    if [ -n "$docker_disk" ]; then
        log_info "Uso de disco Docker: $docker_disk"
    fi
    
    return 0
}

# Function to check logs for errors
check_logs() {
    log_info "Verificando logs recentes..."
    
    local services=$(docker-compose -f $COMPOSE_FILE config --services 2>/dev/null)
    
    for service in $services; do
        local log_errors=$(docker-compose -f $COMPOSE_FILE logs --tail=10 $service 2>/dev/null | grep -i "error\|failed\|exception" | tail -5)
        
        if [ -n "$log_errors" ]; then
            log_warning "Erros encontrados nos logs de $service:"
            echo "$log_errors" | while read line; do
                echo "  - $line"
            done
        else
            log_success "Nenhum erro recente nos logs de $service"
        fi
    done
    
    return 0
}

# Function to test TPM operations
test_tpm_operations() {
    log_info "Testando operações TPM básicas..."
    
    local tpm_services=$(docker-compose -f $COMPOSE_FILE config --services | grep -i tpm || echo "")
    
    for service in $tpm_services; do
        log_info "Testando TPM no serviço $service..."
        
        # Test PCR read
        if docker-compose -f $COMPOSE_FILE exec -T $service tpm2_pcrread sha256:0 &> /dev/null; then
            log_success "Leitura de PCRs funcionando em $service"
        else
            log_error "Falha na leitura de PCRs em $service"
        fi
        
        # Test getting TPM properties
        if docker-compose -f $COMPOSE_FILE exec -T $service tpm2_getcap properties-fixed &> /dev/null; then
            log_success "Consulta de propriedades TPM funcionando em $service"
        else
            log_error "Falha na consulta de propriedades TPM em $service"
        fi
    done
    
    return 0
}

# Main execution function
main() {
    echo "=================================================="
    echo "  Verificação da Infraestrutura Docker TPM + Vault"
    echo "=================================================="
    
    local overall_status=0
    local checks_passed=0
    local checks_total=0
    
    # Run checks
    run_check "Docker e Docker Compose" check_docker
    run_check "Containers" check_containers
    run_check "TPM" check_tpm
    run_check "Vault Status" check_vault
    run_check "Autenticação TPM" check_vault_tpm_auth
    run_check "Rede" check_network
    run_check "Recursos" check_resources
    run_check "Logs" check_logs
    run_check "Operações TPM" test_tpm_operations
    
    echo "=================================================="
    
    # Summary
    if [ $overall_status -eq 0 ]; then
        log_success "$checks_passed/$checks_total verificações passaram - Sistema operacional"
    else
        log_error "$checks_passed/$checks_total verificações passaram - Sistema com problemas"
    fi
    
    exit $overall_status
}

# Helper function to run checks and count results
run_check() {
    local check_name="$1"
    local check_function="$2"
    
    log_info "Executando: $check_name"
    checks_total=$((checks_total + 1))
    
    if $check_function; then
        checks_passed=$((checks_passed + 1))
    else
        overall_status=1
    fi
    
    echo "------------------------------------------"
}

# Handle script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
