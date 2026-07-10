#!/bin/sh
sudo apt-get update  # To get the latest package lists

# Install everything for the rpi-rgb-led-matrix application
sudo apt install git libgraphicsmagick++-dev libwebp-dev -y

# Install everything for the rpi-rgb-led-matrix-frontend application
sudo apt install python3 python3-flask python3-psutil  python3-pil python3-paho-mqtt python3-requests -y

# Go into the home directory
cd
git clone https://github.com/Npmr/rpi-rgb-led-matrix-frontend.git
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git

# Create .gitignore in frontend to exclude local config files
cat > /home/pi/rpi-rgb-led-matrix-frontend/.gitignore << 'EOF'
# Local configuration files (not tracked in git)
settings.json
info.json

# Uploaded images and generated thumbnails
static/pictures/
static/pictures/thumbnails/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
venv/
env/
.env

# Logs
*.log

# PID files
*.pid

# OS files
.DS_Store
Thumbs.db
EOF

# Go into the rpi-rgb-led-matrix directory and build the application
cd rpi-rgb-led-matrix
make -C examples-api-use
cd utils
make led-image-viewer

# Make the Update script executable
cd /home/pi/rpi-rgb-led-matrix-frontend
chmod +x update_application.sh
rm install_application.sh

# Go back into the home directory
cd

# Install the new crontab
(crontab -l 2>/dev/null; echo "@reboot cd /home/pi/rpi-rgb-led-matrix-frontend ; sudo python3 app.py # matrix-frontend-instance ") | crontab -
#reboot the system
sudo reboot