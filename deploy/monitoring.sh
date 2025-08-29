#!/bin/bash

# Monitoring script for Snapped Backend
# This script checks the health of all services and sends alerts if needed

set -e

# Configuration
LOG_FILE="/var/log/snapped/monitoring.log"
ALERT_EMAIL="admin@yourdomain.com"  # Change this to your email
SLACK_WEBHOOK=""  # Add your Slack webhook URL if needed

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

# Alert function
send_alert() {
    local message="$1"
    local severity="$2"
    
    log "ALERT [$severity]: $message"
    
    # Send email alert (requires mailutils to be installed)
    if command -v mail &> /dev/null && [ ! -z "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "Snapped Backend Alert [$severity]" $ALERT_EMAIL
    fi
    
    # Send Slack alert
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 Snapped Backend Alert [$severity]: $message\"}" \
            $SLACK_WEBHOOK
    fi
}

# Check service status
check_service() {
    local service_name="$1"
    
    if systemctl is-active --quiet $service_name; then
        echo -e "${GREEN}✅ $service_name is running${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name is not running${NC}"
        send_alert "$service_name service is down" "CRITICAL"
        return 1
    fi
}

# Check HTTP endpoint
check_http() {
    local url="$1"
    local expected_code="$2"
    local timeout="$3"
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $timeout $url)
    
    if [ "$response_code" = "$expected_code" ]; then
        echo -e "${GREEN}✅ HTTP $url responding with $response_code${NC}"
        return 0
    else
        echo -e "${RED}❌ HTTP $url responding with $response_code (expected $expected_code)${NC}"
        send_alert "HTTP endpoint $url is not responding correctly (got $response_code)" "CRITICAL"
        return 1
    fi
}

# Check disk space
check_disk_space() {
    local threshold="$1"
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -lt "$threshold" ]; then
        echo -e "${GREEN}✅ Disk usage: ${usage}%${NC}"
        return 0
    else
        echo -e "${RED}❌ Disk usage: ${usage}% (threshold: ${threshold}%)${NC}"
        send_alert "Disk usage is high: ${usage}%" "WARNING"
        return 1
    fi
}

# Check memory usage
check_memory() {
    local threshold="$1"
    local usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$usage" -lt "$threshold" ]; then
        echo -e "${GREEN}✅ Memory usage: ${usage}%${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ Memory usage: ${usage}% (threshold: ${threshold}%)${NC}"
        send_alert "Memory usage is high: ${usage}%" "WARNING"
        return 1
    fi
}

# Check Redis
check_redis() {
    if redis-cli ping | grep -q "PONG"; then
        echo -e "${GREEN}✅ Redis is responding${NC}"
        return 0
    else
        echo -e "${RED}❌ Redis is not responding${NC}"
        send_alert "Redis is not responding" "CRITICAL"
        return 1
    fi
}

# Check database
check_database() {
    local db_path="/opt/snapped_backend/app.db"
    
    if [ -f "$db_path" ] && [ -r "$db_path" ]; then
        echo -e "${GREEN}✅ Database file is accessible${NC}"
        return 0
    else
        echo -e "${RED}❌ Database file is not accessible${NC}"
        send_alert "Database file is not accessible" "CRITICAL"
        return 1
    fi
}

# Check log file sizes
check_log_sizes() {
    local max_size_mb="$1"
    local log_dir="/var/log/snapped"
    
    find $log_dir -name "*.log" -size +${max_size_mb}M | while read logfile; do
        local size=$(du -m "$logfile" | cut -f1)
        echo -e "${YELLOW}⚠️ Large log file: $logfile (${size}MB)${NC}"
        send_alert "Log file $logfile is large (${size}MB)" "WARNING"
    done
}

# Check SSL certificate expiration
check_ssl_cert() {
    local domain="$1"
    
    if [ -z "$domain" ]; then
        echo -e "${YELLOW}⚠️ No domain specified for SSL check${NC}"
        return 0
    fi
    
    local expiry_date=$(echo | openssl s_client -servername $domain -connect $domain:443 2>/dev/null | openssl x509 -noout -dates | grep notAfter | cut -d= -f2)
    local expiry_epoch=$(date -d "$expiry_date" +%s)
    local current_epoch=$(date +%s)
    local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    if [ "$days_until_expiry" -gt 30 ]; then
        echo -e "${GREEN}✅ SSL certificate expires in $days_until_expiry days${NC}"
        return 0
    elif [ "$days_until_expiry" -gt 7 ]; then
        echo -e "${YELLOW}⚠️ SSL certificate expires in $days_until_expiry days${NC}"
        send_alert "SSL certificate for $domain expires in $days_until_expiry days" "WARNING"
        return 1
    else
        echo -e "${RED}❌ SSL certificate expires in $days_until_expiry days${NC}"
        send_alert "SSL certificate for $domain expires in $days_until_expiry days" "CRITICAL"
        return 1
    fi
}

# Main monitoring function
main() {
    log "Starting health check..."
    
    local all_checks_passed=true
    
    echo "🔍 Snapped Backend Health Check"
    echo "================================"
    
    # Check system services
    echo -e "\n📋 System Services:"
    check_service "snapped_backend" || all_checks_passed=false
    check_service "nginx" || all_checks_passed=false
    check_service "redis-server" || all_checks_passed=false
    
    # Check HTTP endpoints
    echo -e "\n🌐 HTTP Endpoints:"
    check_http "http://localhost:8000/health" "200" "10" || all_checks_passed=false
    check_http "http://localhost:8000/" "200" "10" || all_checks_passed=false
    
    # Check system resources
    echo -e "\n💻 System Resources:"
    check_disk_space "85" || all_checks_passed=false
    check_memory "90" || all_checks_passed=false
    
    # Check external dependencies
    echo -e "\n🔗 External Dependencies:"
    check_redis || all_checks_passed=false
    check_database || all_checks_passed=false
    
    # Check log files
    echo -e "\n📋 Log Files:"
    check_log_sizes "100"  # 100MB threshold
    
    # Check SSL certificate (if domain is configured)
    if [ ! -z "$1" ]; then
        echo -e "\n🔒 SSL Certificate:"
        check_ssl_cert "$1"
    fi
    
    # Summary
    echo -e "\n📊 Summary:"
    if [ "$all_checks_passed" = true ]; then
        echo -e "${GREEN}✅ All checks passed${NC}"
        log "Health check completed - All systems healthy"
    else
        echo -e "${RED}❌ Some checks failed${NC}"
        log "Health check completed - Issues detected"
    fi
    
    echo ""
    echo "📋 System Information:"
    echo "- Uptime: $(uptime -p)"
    echo "- Load: $(uptime | awk -F'load average:' '{print $2}')"
    echo "- Memory: $(free -h | awk 'NR==2{printf "%s/%s (%.2f%%)", $3,$2,$3*100/$2}')"
    echo "- Disk: $(df -h / | awk 'NR==2{printf "%s/%s (%s)", $3,$2,$5}')"
    
    # Show recent errors from logs
    echo -e "\n📋 Recent Errors (last 10):"
    journalctl -u snapped_backend --since "1 hour ago" --no-pager | grep -i error | tail -10 || echo "No recent errors found"
}

# Run the monitoring
main "$@"