#!/bin/sh
sudo apt-get update

#kill the current instance
ps -ef | grep matrix-frontend-instance | grep -v grep | awk '{print $2}' | xargs kill

#go into the application directory and make a git pull
cd /home/pi/rpi-rgb-led-matrix
git pull
cd /home/pi/rpi-rgb-led-matrix-frontend
git pull

#reboot system with new version installed
sudo reboot