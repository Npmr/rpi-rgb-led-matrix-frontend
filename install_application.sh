#!/bin/sh
sudo apt-get update  # To get the latest package lists

# Install everything for the rpi-rgb-led-matrix application
sudo apt install git libgraphicsmagick++-dev libwebp-dev -y

# Install everything for the rpi-rgb-led-matrix-frontend application
sudo apt install python3 python3-flask python3-psutil  python3-pil -y

# Go into the home directory
cd
git clone https://github.com/Npmr/rpi-rgb-led-matrix-frontend.git
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
# Go into the rpi-rgb-led-matrix directory and build the application
cd rpi-rgb-led-matrix
make -C examples-api-use
cd utils
make led-image-viewer

# Go back into the home directory
cd

# Install the new crontab
(crontab -l 2>/dev/null; echo "@reboot cd /home/pi/rpi-rgb-led-matrix-frontend ; sudo python3 rpi-rgb-led-matrix-frontend/app.py # matrix-frontend-instance ") | crontab -
#reboot the system
sudo reboot