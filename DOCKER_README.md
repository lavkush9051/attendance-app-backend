# Docker Management Scripts for AmeTech HRMS

## Quick Start Commands

### 1. First Time Setup
```powershell
# Copy environment file and configure
cp .env.example .env

# Create necessary directories
mkdir -p face_data uploads logs

# Build and start all services
docker-compose up --build -d
```

### 2. Daily Operations
```powershell
# Start services
docker-compose up -d

# Stop services  
docker-compose down

# View logs
docker-compose logs -f backend

# Restart specific service
docker-compose restart backend
```

### 3. Database Management
```powershell
# Access PostgreSQL directly
docker-compose exec db psql -U postgres -d hrms_db

# Backup database
docker-compose exec db pg_dump -U postgres hrms_db > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T db psql -U postgres hrms_db < backup_file.sql
```

### 4. Development Commands
```powershell
# Rebuild only backend (after code changes)
docker-compose build backend
docker-compose up -d backend

# View real-time backend logs
docker-compose logs -f backend

# Access backend container shell
docker-compose exec backend bash
```

### 5. Cleanup Commands
```powershell
# Stop and remove containers
docker-compose down

# Remove containers and volumes (⚠️ Will delete database)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Complete cleanup (⚠️ Will delete everything)
docker system prune -a
```

## Service URLs
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs  
- **PostgreSQL**: localhost:5432
- **pgAdmin**: http://localhost:5050 (admin@ameisetech.com / admin123)

## Troubleshooting

### Common Issues
1. **Port already in use**: Change ports in docker-compose.yml
2. **Permission denied**: Run as administrator or check file permissions
3. **Database connection failed**: Ensure PostgreSQL container is running
4. **Build failures**: Check Docker daemon is running

### Health Checks
```powershell
# Check all services status
docker-compose ps

# Test backend health
curl http://localhost:8000/health

# Check database connection
docker-compose exec backend python -c "from app.database import engine; print('DB Connected!' if engine else 'DB Failed!')"
```

## Production Deployment

### Environment Variables for Production
```bash
# Update .env file with production values
DATABASE_URL=postgresql://prod_user:secure_password@prod_db_host:5432/prod_hrms_db
SECRET_KEY=your-super-secure-production-jwt-key
DEBUG=False
FRONTEND_URL=https://yourdomain.com
```

### Docker Compose for Production
```yaml
# Use docker-compose.prod.yml for production with:
# - Resource limits
# - Health checks  
# - Restart policies
# - Environment-specific configurations
```