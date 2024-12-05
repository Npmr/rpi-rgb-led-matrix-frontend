#!/bin/sh
sudo apt-get update  # To get the latest package lists
#apt-get install <package name> -y



ps -ef | grep matrix-frontend-instance | grep -v grep | awk '{print $2}' | xargs kill

1. kill the python process
2. git pull or git up from the last release
3. start python process again


wget https://github.com/Npmr/rpi-rgb-led-matrix-frontend.git