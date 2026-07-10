#!/bin/sh
BRANCH="${1:-main}"

LOG_FILE="/home/pi/update_application.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

backup_configs() {
    CONFIG_BACKUP_DIR="/tmp/rpi-rgb-matrix-config-backup-$$"
    mkdir -p "$CONFIG_BACKUP_DIR"
    [ -f "/home/pi/rpi-rgb-led-matrix-frontend/settings.json" ] && cp "/home/pi/rpi-rgb-led-matrix-frontend/settings.json" "$CONFIG_BACKUP_DIR/" && log "Backed up settings.json"
    [ -f "/home/pi/rpi-rgb-led-matrix-frontend/info.json" ] && cp "/home/pi/rpi-rgb-led-matrix-frontend/info.json" "$CONFIG_BACKUP_DIR/" && log "Backed up info.json"
}

restore_configs() {
    [ -f "$CONFIG_BACKUP_DIR/settings.json" ] && cp "$CONFIG_BACKUP_DIR/settings.json" "/home/pi/rpi-rgb-led-matrix-frontend/" && log "Restored settings.json"
    [ -f "$CONFIG_BACKUP_DIR/info.json" ] && cp "$CONFIG_BACKUP_DIR/info.json" "/home/pi/rpi-rgb-led-matrix-frontend/" && log "Restored info.json"
}

cleanup_backup() {
    rm -rf "$CONFIG_BACKUP_DIR"
}

log "Starting update on branch: $BRANCH"

backup_configs

# Update rpi-rgb-led-matrix
log "Updating rpi-rgb-led-matrix..."
cd /home/pi/rpi-rgb-led-matrix || { log "ERROR: rpi-rgb-led-matrix directory not found"; exit 1; }
git fetch --all >> "$LOG_FILE" 2>&1
git checkout "$BRANCH" >> "$LOG_FILE" 2>&1 || git checkout main >> "$LOG_FILE" 2>&1
git reset --hard HEAD >> "$LOG_FILE" 2>&1
git pull >> "$LOG_FILE" 2>&1

# Rebuild led-image-viewer and other utilities
log "Building rpi-rgb-led-matrix..."
make -C examples-api-use >> "$LOG_FILE" 2>&1
cd utils && make led-image-viewer >> "$LOG_FILE" 2>&1
cd /home/pi/rpi-rgb-led-matrix || exit 1

# Rebuild Python bindings
log "Building Python bindings..."
sudo pip install -e . --break-system-packages >> "$LOG_FILE" 2>&1

# Update rpi-rgb-led-matrix-frontend
log "Updating rpi-rgb-led-matrix-frontend..."
cd /home/pi/rpi-rgb-led-matrix-frontend || { log "ERROR: Frontend directory not found"; exit 1; }
git fetch --all >> "$LOG_FILE" 2>&1
git checkout "$BRANCH" >> "$LOG_FILE" 2>&1 || git checkout main >> "$LOG_FILE" 2>&1
git reset --hard HEAD >> "$LOG_FILE" 2>&1
git pull >> "$LOG_FILE" 2>&1

# Make update script executable
chmod +x update_application.sh

restore_configs

# Restart the Flask application (instead of rebooting)
log "Restarting Flask application..."
pkill -f "python3 app.py" >> "$LOG_FILE" 2>&1
sleep 2
nohup sudo python3 app.py > /dev/null 2>&1 &
sleep 2

# Verify the app restarted
if pgrep -f "python3 app.py" > /dev/null; then
    log "Flask application restarted successfully"
else
    log "WARNING: Flask application may not have started properly"
fi

log "Update completed successfully on branch: $BRANCH"

cleanup_backup
