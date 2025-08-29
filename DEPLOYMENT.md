# Snapped Backend - AWS EC2 Deployment Guide

This guide provides comprehensive instructions for deploying the Snapped Backend API on AWS EC2 with optimized performance and production-ready configuration.

## 🚀 Quick Start

For a fully automated deployment, run the installation script on a fresh Ubuntu 22.04 LTS EC2 instance:

```bash
curl -sSL https://raw.githubusercontent.com/your-username/snapped_backend/main/deploy/install.sh | bash
```

## 📋 Prerequisites

### AWS EC2 Instance Requirements

- **Instance Type**: t3.medium or larger (recommended: t3.large for production)
- **Operating System**: Ubuntu 22.04 LTS
- **Storage**: At least 20GB EBS volume
- **Security Group**: Allow inbound traffic on ports 22 (SSH), 80 (HTTP), and 443 (HTTPS)

### Required Services

- **SerpAPI Account**: Sign up at [serpapi.com](https://serpapi.com) for product search functionality
- **Domain Name**: (Optional) For SSL certificate and custom domain
- **Cloudinary Account**: (Optional) For cloud-based image storage

## 🔧 Manual Installation Steps

### 1. Launch EC2 Instance

1. Launch an Ubuntu 22.04 LTS EC2 instance
2. Configure security group with the following inbound rules:
   - SSH (22): Your IP address
   - HTTP (80): 0.0.0.0/0
   - HTTPS (443): 0.0.0.0/0
3. Connect to your instance via SSH

### 2. System Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
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
```

### 3. Application Setup

```bash
# Create application user
sudo useradd -m -s /bin/bash snapped
sudo usermod -aG sudo snapped

# Create directories
sudo mkdir -p /opt/snapped_backend
sudo mkdir -p /var/log/snapped
sudo mkdir -p /var/run/snapped
sudo chown -R snapped:snapped /opt/snapped_backend
sudo chown -R snapped:snapped /var/log/snapped
sudo chown -R snapped:snapped /var/run/snapped

# Clone repository
cd /opt
sudo git clone https://github.com/your-username/snapped_backend.git
sudo chown -R snapped:snapped /opt/snapped_backend
```

### 4. Python Environment

```bash
# Switch to application user
sudo -u snapped bash
cd /opt/snapped_backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Exit back to root user
exit
```

### 5. Configuration

```bash
# Copy production environment file
sudo -u snapped cp /opt/snapped_backend/.env.production /opt/snapped_backend/.env

# Edit configuration (see Configuration section below)
sudo -u snapped nano /opt/snapped_backend/.env
```

### 6. Database Initialization

```bash
# Initialize database
sudo -u snapped bash -c "
cd /opt/snapped_backend
source venv/bin/activate
python -c '
from app.db.init_db import init_db
from app.db.optimize import optimize_database
import asyncio
asyncio.run(init_db())
optimize_database()
'
"
```

### 7. Service Configuration

#### Nginx Configuration

```bash
# Copy nginx configuration
sudo cp /opt/snapped_backend/nginx.conf /etc/nginx/sites-available/snapped_backend
sudo ln -sf /etc/nginx/sites-available/snapped_backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart nginx
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

#### Systemd Service

```bash
# Create systemd service
sudo cp /opt/snapped_backend/deploy/snapped_backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable snapped_backend
sudo systemctl start snapped_backend
```

#### Redis Configuration

```bash
# Enable and start Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 8. Firewall Setup

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

### 9. SSL Certificate (Optional)

```bash
# Install SSL certificate with Let's Encrypt
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## ⚙️ Configuration

### Environment Variables

Edit `/opt/snapped_backend/.env` with your production settings:

```bash
# Production Environment Configuration
ENVIRONMENT=production
DEBUG=false

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database Configuration
DATABASE_URL=sqlite:///./app.db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis Configuration
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# SerpAPI Configuration (REQUIRED)
SERPAPI_API_KEY=your_serpapi_key_here
MAX_SIMILAR_PRODUCTS=30
STORE_RAW_DATA=false

# CORS Configuration
BACKEND_CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Public URL for external services
PUBLIC_BASE_URL=https://yourdomain.com

# Performance Settings
CACHE_TTL=3600
THREAD_POOL_SIZE=8

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production

# Cloudinary Configuration (Optional)
USE_CLOUDINARY=false
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

### Nginx Configuration

Update `/etc/nginx/sites-available/snapped_backend` with your domain:

```nginx
server_name your-domain.com www.your-domain.com;
```

## 🔄 Deployment & Updates

### Initial Deployment

After completing the installation steps above:

```bash
# Check service status
sudo systemctl status snapped_backend
sudo systemctl status nginx
sudo systemctl status redis-server

# Test the API
curl http://your-server-ip/health
```

### Updates

Use the update script for zero-downtime deployments:

```bash
# Run update script
sudo /opt/snapped_backend/deploy/update.sh
```

### Manual Updates

```bash
# Pull latest changes
cd /opt/snapped_backend
sudo -u snapped git pull origin main

# Update dependencies
sudo -u snapped bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Restart service
sudo systemctl restart snapped_backend
```

## 📊 Monitoring & Maintenance

### Health Monitoring

```bash
# Run health check
/opt/snapped_backend/deploy/monitoring.sh your-domain.com

# Check logs
sudo journalctl -u snapped_backend -f
sudo tail -f /var/log/snapped/gunicorn.log
sudo tail -f /var/log/nginx/snapped_access.log
```

### Automated Monitoring

Set up automated monitoring with cron:

```bash
# Add to crontab
sudo crontab -e

# Add these lines:
# Health check every 5 minutes
*/5 * * * * /opt/snapped_backend/deploy/monitoring.sh your-domain.com >> /var/log/snapped/monitoring.log 2>&1

# Daily backup at 2 AM
0 2 * * * /opt/snapped_backend/backup.sh >> /var/log/snapped/backup.log 2>&1
```

### Backup & Recovery

```bash
# Manual backup
/opt/snapped_backend/backup.sh

# Restore from backup
cp /opt/backups/snapped/app_YYYYMMDD_HHMMSS.db /opt/snapped_backend/app.db
sudo systemctl restart snapped_backend
```

## 🚀 Performance Optimizations

The application includes several performance optimizations:

### 1. HTTP Connection Pooling
- Reuses HTTP connections for external API calls
- Reduces latency for SerpAPI requests

### 2. Database Optimizations
- Optimized indexes for search queries
- SQLite performance tuning
- Connection pooling ready for PostgreSQL

### 3. Caching Strategy
- Redis caching for search results
- Configurable TTL for cache entries
- Memory-efficient caching patterns

### 4. Response Compression
- GZip compression for API responses
- Reduces bandwidth usage

### 5. Security Headers
- Production security headers
- CORS configuration
- Rate limiting (via Nginx)

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check logs
sudo journalctl -u snapped_backend -n 50
sudo systemctl status snapped_backend

# Check configuration
sudo -u snapped bash -c "cd /opt/snapped_backend && source venv/bin/activate && python -c 'from app.core.config import settings; print(\"Config loaded successfully\")'"
```

#### Database Issues

```bash
# Reinitialize database
sudo -u snapped bash -c "
cd /opt/snapped_backend
source venv/bin/activate
python -c '
from app.db.init_db import init_db
import asyncio
asyncio.run(init_db())
'
"
```

#### Nginx Issues

```bash
# Test nginx configuration
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
```

#### Redis Issues

```bash
# Check Redis status
sudo systemctl status redis-server
redis-cli ping
```

### Performance Issues

#### High Memory Usage

```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Restart services if needed
sudo systemctl restart snapped_backend
```

#### Slow API Responses

```bash
# Check application logs
sudo journalctl -u snapped_backend -f

# Monitor system resources
htop

# Check Redis performance
redis-cli info stats
```

## 📈 Scaling Considerations

### Horizontal Scaling

For high-traffic applications, consider:

1. **Load Balancer**: Use AWS Application Load Balancer
2. **Multiple Instances**: Deploy on multiple EC2 instances
3. **Database**: Migrate to PostgreSQL or RDS
4. **File Storage**: Use S3 for uploaded images
5. **Caching**: Use ElastiCache for Redis

### Vertical Scaling

For single-instance scaling:

1. **Instance Type**: Upgrade to larger EC2 instance
2. **Workers**: Increase Gunicorn workers
3. **Database**: Optimize queries and indexes
4. **Memory**: Increase Redis memory allocation

## 🔐 Security Best Practices

1. **Keep System Updated**: Regular security updates
2. **Firewall**: Restrict access to necessary ports only
3. **SSL/TLS**: Always use HTTPS in production
4. **Secrets Management**: Use AWS Secrets Manager for sensitive data
5. **Monitoring**: Set up CloudWatch for monitoring
6. **Backups**: Regular automated backups
7. **Access Control**: Use IAM roles and policies

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review application logs
3. Check GitHub issues
4. Contact the development team

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.