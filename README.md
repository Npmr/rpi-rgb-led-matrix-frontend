# rpi-rgb-led-matrix-frontend

A easy to understand frontend to control the rpi-rgb-led-matrix from your mobile device without programming knowledge.

-----
# TODOs
A small list of things that have to be done and wil come in the future for this project.
- Integrate the GIPHY Search API and make it accessible via Home Assistant
- check GIFS from GIPHY to determine if they are horizontal or vertical to display them correct
- get all the settings values into Home Assistant 
- clean up / refactor (this will never get old)
- write some test (only if there is enough time & desire & not new ideas & ...) :stuck_out_tongue_winking_eye:
- rework the installation and update process

# TODOs Done ✔️
- add the GIPHY functionality also into the native frontend of the application ✔️

-----

# Installation Guide

To use this project successfully you need to have the rpi-rgb-led-matrix project on your system. If you dont have that
please use the installer to set up the complete system.
-----

## Installer

This part of the documentation should show how to use the installer and explain what it does
1. Donwload the Script via wget with the following command
   > wget https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/main/install_application.sh
1. change the sh file to be executable
   > chmod +x install_application.sh
2. run the installer file. (!) Because this file uses the SUDO command, you may have to enter your password
   > ./install_application.sh

## Updater

The software can be updated automatically.
To do that please go on the settings page and click the "Update to a new version" Button. This button can only be
clicked when a new Realease of the software is available via GitHub.
This works by running the  update_application.sh Script as a thread in the brackground so that the frontend can still be used until the application is updated. Because then the system will be rebooted. This should be changed in the future. 
