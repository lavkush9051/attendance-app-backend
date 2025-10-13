# Hostinger VPS Deployment (FastAPI + Postgres, Docker)

This guide deploys the backend alongside any existing Docker apps without clashes.

## Prereqs
- Root SSH or sudo user on VPS
- Docker Engine + Docker Compose Plugin installed
- Git installed on VPS

## Create a dedicated Unix user
```bash
# Log in as root
ssh root@<VPS_IP>

# Create user without password (key-based login recommended)
useradd -m -s /bin/bash ameisetech
# Optional: add to docker group to run docker without sudo
usermod -aG docker ameisetech

# Set up SSH for the new user (replace with your public key)
mkdir -p /home/ameisetech/.ssh
chmod 700 /home/ameisetech/.ssh
nano /home/ameisetech/.ssh/authorized_keys
chmod 600 /home/ameisetech/.ssh/authorized_keys
chown -R ameisetech:ameisetech /home/ameisetech/.ssh
```

## Folder layout
- Project root: `/home/ameisetech/hrms-ameisetech`

## Clone & configure
```bash
sudo -iu ameisetech
cd ~

git clone https://github.com/<your-account>/<backend-repo>.git hrms-ameisetech
cd hrms-ameisetech

cp .env.prod.example .env
# IMPORTANT: edit .env to set strong passwords and correct CORS origins
nano .env
```

## Start services (isolated project)
Use a unique project name to avoid collisions: `--project-name hrms-face`.
```bash
# Build and start
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --project-name hrms-face up -d --build

# Check status
docker compose --project-name hrms-face ps

# Tail logs
docker compose --project-name hrms-face logs -f backend
```

## Verify
- Health: `curl http://127.0.0.1:${PUBLIC_PORT:-8081}/health`
- From your browser: `http://<VPS_IP>:8081/health` (open firewall if needed)

## Data & backups
- Postgres data volume: `hrms-face_postgres_data`
- To back up DB:
```bash
# Create a container with pg_dump
docker run --rm --network hrms-face_appnet \
  -e PGPASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d'=' -f2) \
  postgres:13 \
  pg_dump -h db -U postgres -d hrms_db -Fc -f /tmp/hrms_db.backup
```

## Update
```bash
cd /home/ameisetech/hrms-ameisetech
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --project-name hrms-face up -d --build
```

## Optional: Nginx reverse proxy + TLS
If you own a domain (e.g., `api.example.com`), proxy `http://127.0.0.1:8081` and issue Let’s Encrypt.

---

## Local development reminder
- Activate venv: `python -m venv .venv && . .venv/bin/activate` (Windows: `.\.venv\Scripts\Activate.ps1`)
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
