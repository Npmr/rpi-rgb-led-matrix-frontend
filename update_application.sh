#!/bin/sh
#go into the application directory and make a git pull
cd /home/pi/rpi-rgb-led-matrix
git fetch --all
git reset HEAD --hard
git pull

cd /home/pi/rpi-rgb-led-matrix-frontend
cp settings.json /home/pi/settings.json
git fetch --all
git reset HEAD --hard
git pull
chmod +x update_application.sh

# copy the settings file back into the correct folder and remove the bck file afterwards
cd
cp /home/pi/settings.json /home/pi/rpi-rgb-led-matrix-frontend/settings.json
rm settings.json

#reboot system with new version installed
sudo reboot