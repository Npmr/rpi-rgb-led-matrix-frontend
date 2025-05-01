# modules/system_handler.py
import shutil
import subprocess
import os

def getFreeDiskSpace():
    total, used, free = shutil.disk_usage("/")
    return (100 / (total // (2 ** 30))) * (used // (2 ** 30)), (free // (2 ** 30))

def reboot_system():
    os.system('sudo reboot')
    return "Reboot System now!"

def shutdown_system():
    os.system('sudo shutdown -h now')
    return "Shutting down! Bye bye"