#!/bin/bash

# Update script for Snapped Backend on AWS EC2
# Run this script to update the application with zero downtime

set -e

echo "🔄 Starting Snapped Backend update..."

# Change to application directory
cd /opt/snapped_backend

# Backup current version
echo "💾 Creating backup..."
BACKUP_DIR="/opt/backups/snapped/updates"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
cp app.db $BACKUP_DIR/app_${DATE}.db

# Backup current code
tar -czf $BACKUP_DIR/code_${DATE}.tar.gz --exclude=venv --exclude=app.db --exclude=app.db-* .

# Pull latest changes
echo "📥 Pulling latest changes..."
sudo -u snapped git fetch origin
sudo -u snapped git pull origin main

# Update Python dependencies
echo "🐍 Updating Python dependencies..."
sudo -u snapped bash << 'EOF'
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
EOF

# Run database migrations if any
echo "🗄️ Running database optimizations..."
sudo -u snapped bash << 'EOF'
cd /opt/snapped_backend
source venv/bin/activate
python -c "
from app.db.optimize import optimize_database
optimize_database()
"
EOF

# Test configuration
echo "🧪 Testing configuration..."
sudo -u snapped bash << 'EOF'
cd /opt/snapped_backend
source venv/bin/activate
python -c "
from app.core.config import settings
print('Configuration loaded successfully')
print(f'Environment: {settings.ENVIRONMENT}')
print(f'Redis enabled: {settings.REDIS_ENABLED}')
"
EOF

# Restart services with zero downtime
echo "🔄 Restarting services..."

# Restart the application
sudo systemctl reload snapped_backend || sudo systemctl restart snapped_backend

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
sleep 5

# Health check
echo "🏥 Performing health check..."
for i in {1..30}; do
    if curl -s -f http://localhost:8000/health > /dev/null; then
        echo "✅ Service is healthy"
        break
    else
        echo "⏳ Waiting for service... ($i/30)"
        sleep 2
    fi
    
    if [ $i -eq 30 ]; then
        echo "❌ Service failed to start properly"
        echo "🔄 Rolling back..."
        
        # Restore database backup
        cp $BACKUP_DIR/app_${DATE}.db app.db
        
        # Restore code backup
        tar -xzf $BACKUP_DIR/code_${DATE}.tar.gz
        
        # Restart service
        sudo systemctl restart snapped_backend
        
        echo "❌ Update failed and rolled back"
        exit 1
    fi
done

# Reload nginx configuration if changed
if [ -f nginx.conf ]; then
    echo "🌐 Updating Nginx configuration..."
    sudo cp nginx.conf /etc/nginx/sites-available/snapped_backend
    sudo nginx -t && sudo systemctl reload nginx
fi

# Clean up old backups (keep last 10)
echo "🧹 Cleaning up old backups..."
find $BACKUP_DIR -name "*.db" -type f | sort -r | tail -n +11 | xargs rm -f
find $BACKUP_DIR -name "*.tar.gz" -type f | sort -r | tail -n +11 | xargs rm -f

# Final status check
echo "🔍 Final status check..."
sudo systemctl status snapped_backend --no-pager -l

echo ""
echo "🎉 Update completed successfully!"
echo "📊 Service status:"
curl -s http://localhost:8000/health | python3 -m json.tool || echo "Health check endpoint not responding"
echo ""
echo "📋 Useful commands:"
echo "- Check logs: sudo journalctl -u snapped_backend -f"
echo "- Check health: curl http://localhost:8000/health"
echo "- Rollback if needed: restore from $BACKUP_DIR/code_${DATE}.tar.gz"
echo ""