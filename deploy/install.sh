#!/bin/bash
# Snapped Backend — EC2 installer (Ubuntu 22.04)
# - HTTP-only Nginx (no SSL, no redirects)
# - Gunicorn via systemd (no Supervisor)
# - Rate limiting zones in http{} (conf.d)
# - Health & backup scripts
# - UFW, Redis
set -euo pipefail

echo "🚀 Starting Snapped Backend installation..."

# -------- System & packages --------
sudo apt update && sudo apt -y upgrade
sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev python3-pip \
  nginx redis-server git curl wget unzip htop ufw \
  certbot python3-certbot-nginx \
  build-essential libpq-dev libjpeg-dev libpng-dev libfreetype6-dev pkg-config

# -------- App user & dirs --------
if ! id -u snapped >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash snapped
fi
sudo usermod -aG sudo snapped
sudo mkdir -p /opt/snapped_backend /var/log/snapped /var/run/snapped
sudo chown -R snapped:snapped /opt/snapped_backend /var/log/snapped /var/run/snapped

# -------- Repo (edit URL if needed) --------
if [ ! -d /opt/snapped_backend/.git ]; then
  sudo git clone https://github.com/your-username/snapped_backend.git /opt/snapped_backend
  sudo chown -R snapped:snapped /opt/snapped_backend
else
  # Pull the latest changes if the repo already exists
  cd /opt/snapped_backend
  sudo -u snapped git stash --include-untracked
  
  # Pull the latest changes from the main branch
  sudo -u snapped git pull origin main
  
  # Apply the stashed changes back (if any)
  sudo -u snapped git stash pop
fi

# -------- Python env --------
sudo -u snapped bash <<'PYSETUP'
set -euo pipefail
cd /opt/snapped_backend
rm -rf venv  # Remove the existing virtual environment
python3.11 -m venv venv  # Recreate the virtual environment
source venv/bin/activate
pip install --upgrade pip
[ -f requirements.txt ] && pip install -r requirements.txt
# seed .env from production if missing
[ -f .env ] || { [ -f .env.production ] && cp .env.production .env || true; }
PYSETUP

# -------- Redis --------
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# -------- Detect public hostname (fallbacks) --------
get_meta() {
  # Try IMDSv2 then fallback
  TOKEN=$(curl -fsS -m 2 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
  if [ -n "${TOKEN:-}" ]; then
    curl -fsS -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/public-hostname" || true
  else
    curl -fsS -m 2 "http://169.254.169.254/latest/meta-data/public-hostname" || true
  fi
}
HOST="$(get_meta || true)"
[ -z "$HOST" ] && HOST="$(hostname -f || true)"
[ -z "$HOST" ] && HOST="_"
echo "🌐 Using server_name: $HOST"

# -------- Nginx (HTTP only) --------
sudo mkdir -p /etc/nginx/conf.d /etc/nginx/sites-available /etc/nginx/sites-enabled

# http-level rate limits (zones cannot be in server{})
sudo tee /etc/nginx/conf.d/snapped_rate_limit.conf >/dev/null <<'NGX'
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=2r/s;
NGX

# site config (no SSL, no redirect)
sudo tee /etc/nginx/sites-available/snapped_backend >/dev/null <<NGX
server {
    listen 80;
    server_name ${HOST} _;

    client_max_body_size 20M;

    access_log /var/log/nginx/snapped_access.log;
    error_log  /var/log/nginx/snapped_error.log;

    location /static/ {
        alias /opt/snapped_backend/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_set_header Upgrade           \$http_upgrade;
        proxy_set_header Connection        "upgrade";

        proxy_connect_timeout 30s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
        proxy_buffering off;
    }

    location = /api/v1/images/upload {
        limit_req zone=upload burst=5 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade           \$http_upgrade;
        proxy_set_header Connection        "upgrade";

        proxy_connect_timeout 60s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;
        proxy_buffering off;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade           \$http_upgrade;
        proxy_set_header Connection        "upgrade";

        proxy_connect_timeout 30s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }
}
NGX

sudo ln -sf /etc/nginx/sites-available/snapped_backend /etc/nginx/sites-enabled/snapped_backend
sudo rm -f /etc/nginx/sites-enabled/default

# Nuke any stray SSL directives / 443 listeners from older files
sudo sed -i -E 's/^\s*(ssl_certificate(_key)?\s+)/# \1/' /etc/nginx/nginx.conf || true
sudo sed -i -E 's/^\s*(ssl_certificate(_key)?\s+)/# \1/' /etc/nginx/sites-available/* 2>/dev/null || true
sudo sed -i -E 's/^\s*(ssl_certificate(_key)?\s+)/# \1/' /etc/nginx/conf.d/*.conf 2>/dev/null || true
sudo sed -i -E 's/^\s*listen\s+443(.*)$/# listen 443 \1/' /etc/nginx/sites-available/* 2>/dev/null || true
sudo sed -i -E 's/^\s*listen\s+\[::\]:443(.*)$/# listen [::]:443 \1/' /etc/nginx/sites-available/* 2>/dev/null || true

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# -------- Gunicorn via systemd --------
sudo tee /etc/systemd/system/snapped_backend.service >/dev/null <<'UNIT'
[Unit]
Description=Snapped Backend API (Gunicorn)
After=network.target

[Service]
Type=simple
User=snapped
Group=snapped
WorkingDirectory=/opt/snapped_backend
Environment=PATH=/opt/snapped_backend/venv/bin
ExecStart=/opt/snapped_backend/venv/bin/gunicorn -c /opt/snapped_backend/gunicorn.conf.py app.main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable snapped_backend
sudo systemctl restart snapped_backend

# -------- UFW --------
sudo ufw allow ssh
sudo ufw allow 'Nginx HTTP'
sudo ufw --force enable

# -------- Flip HTTPS->HTTP in env (CORS/links) --------
for f in /opt/snapped_backend/.env.production /opt/snapped_backend/.env.production; do
  if [ -f "$f" ]; then
    sudo sed -i -E 's#^(BACKEND_CORS_ORIGINS=)https://#\1http://#' "$f" || true
    sudo sed -i -E 's#^(PUBLIC_BASE_URL=)https://#\1http://#' "$f" || true
  fi
done
sudo systemctl restart snapped_backend

# -------- DB init (safe) --------
sudo -u snapped bash <<'DBINIT'
set -euo pipefail
cd /opt/snapped_backend
source venv/bin/activate
python - <<'PY'
import asyncio
try:
    from app.db.init_db import init_db
    from app.db.optimize import optimize_database
except Exception as e:
    print("Skipping DB init:", e)
else:
    asyncio.run(init_db())
    optimize_database()
PY
DBINIT

# -------- Logrotate --------
sudo tee /etc/logrotate.d/snapped_backend >/dev/null <<'ROT'
/var/log/snapped/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 0644 snapped snapped
    postrotate
        systemctl reload snapped_backend >/dev/null 2>&1 || true
    endscript
}
ROT

# -------- Health script --------
sudo tee /opt/snapped_backend/health_check.sh >/dev/null <<'HCHK'
#!/bin/bash
set -e
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
if [ "$response" -eq 200 ]; then
  echo "✅ Service is healthy"
else
  echo "❌ Service is unhealthy (HTTP $response)"
  exit 1
fi
HCHK
sudo chmod +x /opt/snapped_backend/health_check.sh

# -------- Backup script (SQLite example) --------
sudo tee /opt/snapped_backend/backup.sh >/dev/null <<'BKP'
#!/bin/bash
set -euo pipefail
BACKUP_DIR="/opt/backups/snapped"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

[ -f /opt/snapped_backend/app.db ] && cp /opt/snapped_backend/app.db "$BACKUP_DIR/app_${DATE}.db"
[ -d /opt/snapped_backend/app/static/uploads ] && \
  tar -czf "$BACKUP_DIR/uploads_${DATE}.tar.gz" -C /opt/snapped_backend/app/static uploads/

find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete || true
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete || true
echo "Backup completed: $DATE"
BKP
sudo chmod +x /opt/snapped_backend/backup.sh
( sudo crontab -l 2>/dev/null; echo "0 2 * * * /opt/snapped_backend/backup.sh >> /var/log/snapped/backup.log 2>&1" ) | sudo crontab -

# -------- Final status --------
echo "🔍 Services:"
sudo systemctl --no-pager status snapped_backend || true
sudo systemctl --no-pager status nginx || true
sudo systemctl --no-pager status redis-server || true

echo "✅ Done. Site is HTTP-only on: http://$HOST"
