#!/bin/sh
BRANCH="${1:-main}"

LOG_FILE="/home/pi/update_application.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

backup_configs() {
    CONFIG_BACKUP_DIR="/tmp/rpi-rgb-matrix-config-backup-$$"
    mkdir -p "$CONFIG_BACKUP_DIR"
    for CONFIG_FILE in settings.json layout.json; do
        if [ -f "/home/pi/rpi-rgb-led-matrix-frontend/$CONFIG_FILE" ]; then
            cp "/home/pi/rpi-rgb-led-matrix-frontend/$CONFIG_FILE" "$CONFIG_BACKUP_DIR/"
            log "Backed up $CONFIG_FILE"
        fi
    done
}

restore_configs() {
    for CONFIG_FILE in settings.json layout.json; do
        if [ -f "$CONFIG_BACKUP_DIR/$CONFIG_FILE" ]; then
            cp "$CONFIG_BACKUP_DIR/$CONFIG_FILE" "/home/pi/rpi-rgb-led-matrix-frontend/"
            log "Restored $CONFIG_FILE"
        fi
    done
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

# Ensure the Python bindings used by the grid renderer are available.
# Since February 2026 the bindings use scikit-build-core + CMake and must be
# installed from the repository root; bindings/python has no setup.py or
# pyproject.toml anymore. Check with sudo because the app runs as root.
log "Ensuring rgbmatrix Python bindings..."
if ! sudo python3 -c "import rgbmatrix" > /dev/null 2>&1; then
    if ! command -v cmake > /dev/null 2>&1 || ! command -v cython3 > /dev/null 2>&1; then
        log "Installing Python bindings build dependencies..."
        sudo apt-get install -y python3-dev python3-pip cython3 cmake build-essential >> "$LOG_FILE" 2>&1
    fi
    cd /home/pi/rpi-rgb-led-matrix || exit 1
    if [ -f pyproject.toml ]; then
        (sudo pip3 install --break-system-packages . || sudo pip3 install .) >> "$LOG_FILE" 2>&1 \
            || log "WARNING: could not install rgbmatrix Python bindings (grid display unavailable)"
    else
        cd bindings/python || exit 1
        (sudo pip3 install --break-system-packages . || sudo pip3 install .) >> "$LOG_FILE" 2>&1 \
            || log "WARNING: could not install rgbmatrix Python bindings (grid display unavailable)"
        cd /home/pi/rpi-rgb-led-matrix || exit 1
    fi
    sudo python3 -c "import rgbmatrix" > /dev/null 2>&1 \
        || log "WARNING: rgbmatrix still not importable after install (see pip output above)"
fi

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