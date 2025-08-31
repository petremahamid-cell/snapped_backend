#!/bin/bash

# AWS EC2 Installation Script for Snapped Backend
# Run this script on a fresh Ubuntu 22.04 LTS EC2 instance

set -e

echo "🚀 Starting Snapped Backend installation on AWS EC2..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    nginx \
    redis-server \
    git \
    curl \
    wget \
    unzip \
    supervisor \
    htop \
    ufw \
    certbot \
    python3-certbot-nginx \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    pkg-config

# Create application user
echo "👤 Creating application user..."
sudo useradd -m -s /bin/bash snapped || true
sudo usermod -aG sudo snapped

# Create application directories
echo "📁 Creating application directories..."
sudo mkdir -p /opt/snapped_backend
sudo mkdir -p /var/log/snapped
sudo mkdir -p /var/run/snapped
sudo chown -R snapped:snapped /opt/snapped_backend
sudo chown -R snapped:snapped /var/log/snapped
sudo chown -R snapped:snapped /var/run/snapped

# Clone the repository (you'll need to replace with your actual repo)
echo "📥 Cloning repository..."
cd /opt
sudo git clone https://github.com/your-username/snapped_backend.git || true
sudo chown -R snapped:snapped /opt/snapped_backend

# Switch to application user for Python setup
echo "🐍 Setting up Python environment..."
sudo -u snapped bash << 'EOF'
cd /opt/snapped_backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Create production environment file
cp .env.production .env
EOF

# Configure Redis
echo "🔴 Configuring Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Configure Nginx
echo "🌐 Configuring Nginx..."
sudo cp /opt/snapped_backend/nginx.conf /etc/nginx/sites-available/snapped_backend
sudo ln -sf /etc/nginx/sites-available/snapped_backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Define rate limit zones in http context (not inside server block)
sudo mkdir -p /etc/nginx/conf.d
sudo tee /etc/nginx/conf.d/snapped_rate_limit.conf > /dev/null << 'EOF'
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=2r/s;
EOF

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# Configure Supervisor for Gunicorn
echo "👮 Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/snapped_backend.conf > /dev/null << 'EOF'
[program:snapped_backend]
command=/opt/snapped_backend/venv/bin/gunicorn -c /opt/snapped_backend/gunicorn.conf.py app.main:app
directory=/opt/snapped_backend
user=snapped
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/snapped/gunicorn.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=PATH="/opt/snapped_backend/venv/bin"
EOF

sudo supervisorctl reread
sudo supervisorctl update
sudo systemctl enable supervisor
sudo systemctl start supervisor

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# Initialize database
echo "🗄️ Initializing database..."
sudo -u snapped bash << 'EOF'
cd /opt/snapped_backend
source venv/bin/activate
python -c "
from app.db.init_db import init_db
from app.db.optimize import optimize_database
import asyncio
asyncio.run(init_db())
optimize_database()
"
EOF

# Create systemd service for the application (alternative to supervisor)
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/snapped_backend.service > /dev/null << 'EOF'
[Unit]
Description=Snapped Backend API
After=network.target

[Service]
Type=exec
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
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable snapped_backend
sudo systemctl start snapped_backend

# Create log rotation
echo "📋 Setting up log rotation..."
sudo tee /etc/logrotate.d/snapped_backend > /dev/null << 'EOF'
/var/log/snapped/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 snapped snapped
    postrotate
        systemctl reload snapped_backend
    endscript
}
EOF

# Create health check script
echo "🏥 Creating health check script..."
sudo tee /opt/snapped_backend/health_check.sh > /dev/null << 'EOF'
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ $response -eq 200 ]; then
    echo "✅ Service is healthy"
    exit 0
else
    echo "❌ Service is unhealthy (HTTP $response)"
    exit 1
fi
EOF

sudo chmod +x /opt/snapped_backend/health_check.sh

# Create backup script
echo "💾 Creating backup script..."
sudo tee /opt/snapped_backend/backup.sh > /dev/null << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/snapped"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp /opt/snapped_backend/app.db $BACKUP_DIR/app_${DATE}.db

# Backup uploaded files
tar -czf $BACKUP_DIR/uploads_${DATE}.tar.gz -C /opt/snapped_backend/app/static uploads/

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

sudo chmod +x /opt/snapped_backend/backup.sh

# Add backup to crontab
echo "⏰ Setting up automated backups..."
(sudo crontab -l 2>/dev/null; echo "0 2 * * * /opt/snapped_backend/backup.sh >> /var/log/snapped/backup.log 2>&1") | sudo crontab -

# Final status check
echo "🔍 Checking service status..."
sudo systemctl status snapped_backend --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status redis-server --no-pager

echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Update /opt/snapped_backend/.env with your actual configuration"
echo "2. Update nginx.conf with your domain name"
echo "3. Set up SSL certificate with: sudo certbot --nginx -d your-domain.com"
echo "4. Restart services: sudo systemctl restart snapped_backend nginx"
echo "5. Test the API: curl http://your-server-ip/health"
echo ""
echo "📊 Useful commands:"
echo "- Check logs: sudo journalctl -u snapped_backend -f"
echo "- Restart service: sudo systemctl restart snapped_backend"
echo "- Check health: /opt/snapped_backend/health_check.sh"
echo "- Manual backup: /opt/snapped_backend/backup.sh"
echo ""
echo "🔧 Configuration files:"
echo "- App config: /opt/snapped_backend/.env"
echo "- Nginx config: /etc/nginx/sites-available/snapped_backend"
echo "- Gunicorn config: /opt/snapped_backend/gunicorn.conf.py"
echo ""