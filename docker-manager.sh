#!/bin/bash

# AmeTech HRMS Docker Management Script
# Usage: ./docker-manager.sh [command]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="ameisetech-hrms"

# Helper functions
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

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Setup initial environment
setup() {
    log_info "Setting up AmeTech HRMS environment..."
    
    # Copy environment file if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        log_success "Created .env file from template"
        log_warning "Please update .env with your actual configuration"
    fi
    
    # Create required directories
    mkdir -p face_data uploads logs
    touch face_data/.gitkeep uploads/.gitkeep logs/.gitkeep
    
    log_success "Environment setup completed!"
}

# Build and start services
start() {
    log_info "Starting AmeTech HRMS services..."
    check_docker
    
    docker-compose -f $COMPOSE_FILE up -d
    
    log_success "Services started successfully!"
    log_info "Backend API: http://localhost:8000"
    log_info "API Docs: http://localhost:8000/docs"
    log_info "pgAdmin: http://localhost:5050"
}

# Build services
build() {
    log_info "Building AmeTech HRMS services..."
    check_docker
    
    docker-compose -f $COMPOSE_FILE build $1
    
    log_success "Build completed!"
}

# Stop services
stop() {
    log_info "Stopping AmeTech HRMS services..."
    
    docker-compose -f $COMPOSE_FILE down
    
    log_success "Services stopped!"
}

# Restart services
restart() {
    log_info "Restarting AmeTech HRMS services..."
    
    docker-compose -f $COMPOSE_FILE restart $1
    
    log_success "Services restarted!"
}

# View logs
logs() {
    service=${1:-backend}
    log_info "Showing logs for $service..."
    
    docker-compose -f $COMPOSE_FILE logs -f $service
}

# Check status
status() {
    log_info "Checking service status..."
    
    docker-compose -f $COMPOSE_FILE ps
    
    # Health check
    echo
    log_info "Health check results:"
    
    if curl -s http://localhost:8000/health > /dev/null; then
        log_success "Backend API is healthy"
    else
        log_error "Backend API is not responding"
    fi
    
    if docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
        log_success "Database is healthy"
    else
        log_error "Database is not responding"
    fi
}

# Database operations
db_shell() {
    log_info "Connecting to PostgreSQL shell..."
    docker-compose exec db psql -U postgres -d hrms_db
}

db_backup() {
    backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    log_info "Creating database backup: $backup_file"
    
    docker-compose exec -T db pg_dump -U postgres hrms_db > $backup_file
    
    log_success "Database backup created: $backup_file"
}

db_restore() {
    if [ -z "$1" ]; then
        log_error "Please provide backup file path"
        log_info "Usage: $0 db-restore <backup_file.sql>"
        exit 1
    fi
    
    if [ ! -f "$1" ]; then
        log_error "Backup file not found: $1"
        exit 1
    fi
    
    log_warning "This will overwrite the current database. Continue? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Database restore cancelled"
        exit 0
    fi
    
    log_info "Restoring database from: $1"
    docker-compose exec -T db psql -U postgres hrms_db < $1
    
    log_success "Database restored successfully!"
}

# Cleanup operations
clean() {
    log_warning "This will stop and remove all containers. Continue? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled"
        exit 0
    fi
    
    log_info "Cleaning up containers..."
    docker-compose -f $COMPOSE_FILE down
    
    log_success "Cleanup completed!"
}

clean_all() {
    log_error "This will remove all containers, volumes, and images. ALL DATA WILL BE LOST!"
    log_warning "Continue? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Full cleanup cancelled"
        exit 0
    fi
    
    log_info "Removing all containers, volumes, and images..."
    docker-compose -f $COMPOSE_FILE down -v --rmi all
    
    log_success "Full cleanup completed!"
}

# Show help
show_help() {
    echo "AmeTech HRMS Docker Management Script"
    echo
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  setup           Setup initial environment and directories"
    echo "  start           Start all services"
    echo "  stop            Stop all services"
    echo "  restart [svc]   Restart services (or specific service)"
    echo "  build [svc]     Build services (or specific service)"
    echo "  logs [svc]      Show logs (default: backend)"
    echo "  status          Show service status and health"
    echo "  db-shell        Open PostgreSQL shell"
    echo "  db-backup       Create database backup"
    echo "  db-restore <file>  Restore database from backup"
    echo "  clean           Stop and remove containers"
    echo "  clean-all       Remove everything (⚠️  DATA LOSS)"
    echo "  help            Show this help"
    echo
    echo "Examples:"
    echo "  $0 setup"
    echo "  $0 start"
    echo "  $0 logs backend"
    echo "  $0 restart backend"
    echo "  $0 db-backup"
    echo "  $0 db-restore backup_20240101.sql"
}

# Main command handler
case "$1" in
    setup)
        setup
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart $2
        ;;
    build)
        build $2
        ;;
    logs)
        logs $2
        ;;
    status)
        status
        ;;
    db-shell)
        db_shell
        ;;
    db-backup)
        db_backup
        ;;
    db-restore)
        db_restore $2
        ;;
    clean)
        clean
        ;;
    clean-all)
        clean_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac