# AmeTech HRMS Docker Management Script (Windows PowerShell)
# Usage: .\docker-manager.ps1 [command]

param(
    [string]$Command = "",
    [string]$Service = "",
    [string]$BackupFile = ""
)

# Configuration
$ComposeFile = "docker-compose.yml"
$ProjectName = "ameisetech-hrms"

# Colors for output
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# Check if Docker is running
function Test-Docker {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        Write-Error "Docker is not running. Please start Docker and try again."
        exit 1
    }
}

# Setup initial environment
function Setup-Environment {
    Write-Info "Setting up AmeTech HRMS environment..."
    
    # Copy environment file if it doesn't exist
    if (!(Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Success "Created .env file from template"
        Write-Warning "Please update .env with your actual configuration"
    }
    
    # Create required directories
    @("face_data", "uploads", "logs") | ForEach-Object {
        if (!(Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
            New-Item -ItemType File -Path "$_\.gitkeep" -Force | Out-Null
        }
    }
    
    Write-Success "Environment setup completed!"
}

# Build and start services
function Start-Services {
    Write-Info "Starting AmeTech HRMS services..."
    Test-Docker
    
    docker-compose -f $ComposeFile up -d
    
    Write-Success "Services started successfully!"
    Write-Info "Backend API: http://localhost:8000"
    Write-Info "API Docs: http://localhost:8000/docs"
    Write-Info "pgAdmin: http://localhost:5050"
}

# Build services
function Build-Services {
    param([string]$ServiceName = "")
    
    Write-Info "Building AmeTech HRMS services..."
    Test-Docker
    
    if ($ServiceName) {
        docker-compose -f $ComposeFile build $ServiceName
    } else {
        docker-compose -f $ComposeFile build
    }
    
    Write-Success "Build completed!"
}

# Stop services
function Stop-Services {
    Write-Info "Stopping AmeTech HRMS services..."
    
    docker-compose -f $ComposeFile down
    
    Write-Success "Services stopped!"
}

# Restart services
function Restart-Services {
    param([string]$ServiceName = "")
    
    Write-Info "Restarting AmeTech HRMS services..."
    
    if ($ServiceName) {
        docker-compose -f $ComposeFile restart $ServiceName
    } else {
        docker-compose -f $ComposeFile restart
    }
    
    Write-Success "Services restarted!"
}

# View logs
function Show-Logs {
    param([string]$ServiceName = "backend")
    
    Write-Info "Showing logs for $ServiceName..."
    
    docker-compose -f $ComposeFile logs -f $ServiceName
}

# Check status
function Show-Status {
    Write-Info "Checking service status..."
    
    docker-compose -f $ComposeFile ps
    
    # Health check
    Write-Host ""
    Write-Info "Health check results:"
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Success "Backend API is healthy"
        }
    }
    catch {
        Write-Error "Backend API is not responding"
    }
    
    try {
        $dbCheck = docker-compose exec -T db pg_isready -U postgres 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Database is healthy"
        }
    }
    catch {
        Write-Error "Database is not responding"
    }
}

# Database operations
function Open-DatabaseShell {
    Write-Info "Connecting to PostgreSQL shell..."
    docker-compose exec db psql -U postgres -d hrms_db
}

function Backup-Database {
    $backupFile = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
    Write-Info "Creating database backup: $backupFile"
    
    docker-compose exec -T db pg_dump -U postgres hrms_db | Out-File -FilePath $backupFile -Encoding UTF8
    
    Write-Success "Database backup created: $backupFile"
}

function Restore-Database {
    param([string]$BackupFilePath)
    
    if (!$BackupFilePath) {
        Write-Error "Please provide backup file path"
        Write-Info "Usage: .\docker-manager.ps1 db-restore -BackupFile <backup_file.sql>"
        exit 1
    }
    
    if (!(Test-Path $BackupFilePath)) {
        Write-Error "Backup file not found: $BackupFilePath"
        exit 1
    }
    
    Write-Warning "This will overwrite the current database. Continue? (y/N)"
    $response = Read-Host
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Database restore cancelled"
        exit 0
    }
    
    Write-Info "Restoring database from: $BackupFilePath"
    Get-Content $BackupFilePath | docker-compose exec -T db psql -U postgres hrms_db
    
    Write-Success "Database restored successfully!"
}

# Cleanup operations
function Clean-Containers {
    Write-Warning "This will stop and remove all containers. Continue? (y/N)"
    $response = Read-Host
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Cleanup cancelled"
        exit 0
    }
    
    Write-Info "Cleaning up containers..."
    docker-compose -f $ComposeFile down
    
    Write-Success "Cleanup completed!"
}

function Clean-Everything {
    Write-Error "This will remove all containers, volumes, and images. ALL DATA WILL BE LOST!"
    Write-Warning "Continue? (y/N)"
    $response = Read-Host
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Full cleanup cancelled"
        exit 0
    }
    
    Write-Info "Removing all containers, volumes, and images..."
    docker-compose -f $ComposeFile down -v --rmi all
    
    Write-Success "Full cleanup completed!"
}

# Show help
function Show-Help {
    Write-Host "AmeTech HRMS Docker Management Script (PowerShell)"
    Write-Host ""
    Write-Host "Usage: .\docker-manager.ps1 [command] -Service [service] -BackupFile [file]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  setup           Setup initial environment and directories"
    Write-Host "  start           Start all services"
    Write-Host "  stop            Stop all services"
    Write-Host "  restart         Restart services (use -Service for specific service)"
    Write-Host "  build           Build services (use -Service for specific service)"
    Write-Host "  logs            Show logs (use -Service, default: backend)"
    Write-Host "  status          Show service status and health"
    Write-Host "  db-shell        Open PostgreSQL shell"
    Write-Host "  db-backup       Create database backup"
    Write-Host "  db-restore      Restore database from backup (use -BackupFile)"
    Write-Host "  clean           Stop and remove containers"
    Write-Host "  clean-all       Remove everything (⚠️  DATA LOSS)"
    Write-Host "  help            Show this help"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\docker-manager.ps1 setup"
    Write-Host "  .\docker-manager.ps1 start"
    Write-Host "  .\docker-manager.ps1 logs -Service backend"
    Write-Host "  .\docker-manager.ps1 restart -Service backend"
    Write-Host "  .\docker-manager.ps1 db-backup"
    Write-Host "  .\docker-manager.ps1 db-restore -BackupFile backup_20240101.sql"
}

# Main command handler
switch ($Command.ToLower()) {
    "setup" { Setup-Environment }
    "start" { Start-Services }
    "stop" { Stop-Services }
    "restart" { Restart-Services -ServiceName $Service }
    "build" { Build-Services -ServiceName $Service }
    "logs" { Show-Logs -ServiceName $(if ($Service) { $Service } else { "backend" }) }
    "status" { Show-Status }
    "db-shell" { Open-DatabaseShell }
    "db-backup" { Backup-Database }
    "db-restore" { Restore-Database -BackupFilePath $BackupFile }
    "clean" { Clean-Containers }
    "clean-all" { Clean-Everything }
    "help" { Show-Help }
    default {
        if ($Command) {
            Write-Error "Unknown command: $Command"
            Write-Host ""
        }
        Show-Help
        if ($Command) { exit 1 }
    }
}