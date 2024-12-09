import json
import os
import shutil
import subprocess
from threading import Thread

import psutil
from PIL import Image
from flask import Flask, render_template, request, url_for, redirect

from upload_handler import upload_image

app = Flask(__name__)
app.config['STATIC_FOLDER'] = 'static/pictures'


def read_settings(filename="settings.json"):
    with open(filename, 'r') as f:
        settings = json.load(f)
    return settings


def read_infos(filename="info.json"):
    with open(filename, 'r') as f:
        app_info = json.load(f)
    return app_info


@app.route('/')
def index():
    medias = countMediaTypeAndNumber()

    return render_template('index.html', images=medias[0], gifs=medias[1])


@app.route('/upload')
def upload():
    freeDiskSpaceInPercent = getFreeDiskSpace()

    return render_template('upload.html', freeDiskSpaceInPercent=round(freeDiskSpaceInPercent[0]))


@app.route('/delete_image', methods=['POST'])
def delete_image():
    image_name = request.form['image_name_to_delete']
    image_path = os.path.join(app.config['STATIC_FOLDER'], image_name)

    try:
        os.remove(image_path)
        return redirect(url_for('index'))
    except OSError as e:
        return redirect(url_for('index'))


@app.route('/settings')
def settings():
    settings = read_settings()
    medias = countMediaTypeAndNumber()
    numberOfPictues = len(medias[0])
    numberOfGifs = len(medias[1])
    freeDiskSpaceInPercent = getFreeDiskSpace()

    infos = read_infos()

    return render_template('settings.html', settings=settings, numberOfPictues=numberOfPictues,
                           numberOfGifs=numberOfGifs, freeDiskSpaceInPercent=round(freeDiskSpaceInPercent[0]),
                           applicationInfo=infos)


@app.route('/save_settings', methods=['POST'])
def save_settings():
    new_height = request.form['height']
    new_width = request.form['width']
    new_direction = request.form['direction']
    new_chainLength = request.form['chainLength']
    new_parallelChains = request.form['parallelChains']
    new_ledSlowdown = request.form['ledSlowdown']
    new_playlistTime = request.form['playlistTime']

    # Update the settings.json file
    with open('settings.json', 'w') as f:
        json.dump({'heightInPixel': new_height, 'widthInPixel': new_width, 'direction': new_direction,
                   'chainLength': new_chainLength, 'parallelChains': new_parallelChains, 'ledSlowdown': new_ledSlowdown,
                   'playlistTime': new_playlistTime}, f, indent=4)
    return 'Changes saved'


@app.route('/process_image', methods=['POST'])
def process_image():
    image_name = request.form['image_name']

    process_thread = Thread(target=process_image_async, args=(image_name,))
    process_thread.start()

    return 'Das Bild sollte in Kürze erscheinen. <a href=\"/\">Zurück zur Übersicht</a>'


@app.route('/stop_process', methods=['POST'])
def stop_process():
    # Implement logic to stop the running process
    # Use psutil to find and terminate the process
    for process in psutil.process_iter():
        if "led-image-viewer" in process.name():
            process.kill()
            return redirect(url_for('index'))  # Update success message
    return 'No process found to stop.'


def process_image_async(image_name):
    # Check for existing process
    for process in psutil.process_iter():
        if "led-image-viewer" in process.name():
            process.kill()
            break

    settings = read_settings()
    rotation = ";Rotate:270"
    if settings["direction"] == "horizontal":
        rotation = ";Rotate:180"
    if settings["direction"] == "verticalTurned":
        rotation = ";Rotate:90"
    if settings["direction"] == "horizontalTurned":
        rotation = ";Rotate:0"

    command = f"sudo .././rpi-rgb-led-matrix/utils/led-image-viewer -C --led-no-hardware-pulse --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness=50 --led-pixel-mapper=\"U-mapper{rotation}\" --led-slowdown-gpio={settings['ledSlowdown']} /home/pi/rpi-rgb-led-matrix-frontend/static/pictures/{image_name} &"

    # Start the new process
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Capture standard output and error (optional) in a separate thread
    def capture_output():
        stdout, stderr = process.communicate()
        if stdout:
            print(f"Process output: {stdout.decode()}")
        if stderr:
            print(f"Process error: {stderr.decode()}")

    output_thread = Thread(target=capture_output)
    output_thread.start()


def getFreeDiskSpace():
    total, used, free = shutil.disk_usage("/")

    print("Total: %d GiB" % (total // (2 ** 30)))
    print("Used: %d GiB" % (used // (2 ** 30)))
    print("Free: %d GiB" % (free // (2 ** 30)))
    return (100 / (total // (2 ** 30))) * (used // (2 ** 30)), (free // (2 ** 30))


def determine_orientation(image_path):
    with Image.open(image_path) as img:
        width, height = img.size
        if width > height:
            return "horizontal"
        elif height > width:
            return "vertical"
        else:
            return "square"


def countMediaTypeAndNumber():
    image_files = os.listdir('static/pictures')

    images = []
    gifs = []

    for file in image_files:
        image_path = os.path.join('static/pictures', file)
        orientation = determine_orientation(image_path)

        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            images.append({'filename': file, 'orientation': orientation})
        elif file.lower().endswith('.gif'):
            gifs.append({'filename': file, 'orientation': orientation})
    return images, gifs


upload_image(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
