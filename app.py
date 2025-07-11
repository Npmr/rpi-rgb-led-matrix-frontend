import os
from flask import Flask, render_template, request, url_for, redirect, jsonify
from threading import Thread

from upload_handler import upload_image
from modules.settings_handler import read_settings, save_settings
from modules.info_handler import read_infos
from modules.media_handler import countMediaTypeAndNumber
from modules.display_control import process_image_async, stopProcess
from modules.system_handler import getFreeDiskSpace, reboot_system, shutdown_system
from modules.update_handler import trigger_update, fetch_update_info
from modules import mqtt_handler, giphy_controller

app = Flask(__name__)
app.config['STATIC_FOLDER'] = 'static/pictures'


def handle_play_media(image_name):
    process_thread = Thread(target=process_image_async, args=(image_name, "displayImage", app.config['STATIC_FOLDER']))
    process_thread.start()


def handle_stop():
    stopProcess()


@app.route('/')
def index():
    medias = countMediaTypeAndNumber(app.config['STATIC_FOLDER'])
    return render_template('index.html', images=medias[0], gifs=medias[1], videos=medias[2])


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


@app.route('/start_giphy_web', methods=['POST'])
def start_giphy_web():
    print("Web request received to start Giphy")
    giphy_controller.start_giphy_loop()
    return redirect(url_for('index'))


@app.route('/get_art_design_subcategories')
def get_art_design_subcategories():
    subcategories = giphy_controller.get_art_design_subcategories()
    return jsonify(subcategories)


@app.route('/start_giphy_category', methods=['POST'])
def start_giphy_category():
    category_encoded = request.form.get('giphy_category')
    if category_encoded:
        print(f"Web request received to start Giphy for category: {category_encoded}")
        giphy_controller.start_giphy_loop(search_term=category_encoded)
        return redirect(url_for('index'))
    else:
        return "Error: No category selected.", 400


@app.route('/settings')
def settings():
    settings = read_settings()
    medias = countMediaTypeAndNumber(app.config['STATIC_FOLDER'])
    numberOfPictues = len(medias[0])
    numberOfGifs = len(medias[1])
    freeDiskSpaceInPercent = getFreeDiskSpace()
    infos = read_infos()
    update_info = fetch_update_info()

    updateVersion = update_info.get('currentApplicationVersion') if update_info else 'unknown'
    updateText = update_info.get('whatChanged') if update_info else ''
    currentVersion = infos.get('currentApplicationVersion', 'unknown')

    enableUpdateButton = "" if updateVersion != currentVersion and update_info else "disabled"

    return render_template('settings.html', settings=settings, numberOfPictues=numberOfPictues,
                           numberOfGifs=numberOfGifs, freeDiskSpaceInPercent=round(freeDiskSpaceInPercent[0]),
                           applicationInfo=infos, updateText=updateText, currentAvailableVersion=updateVersion,
                           enableUpdateButton=enableUpdateButton)


@app.route('/save_settings', methods=['POST'])
def save_settings_route():
    new_height = request.form['height']
    new_width = request.form['width']
    new_direction = request.form['direction']
    new_chainLength = request.form['chainLength']
    new_parallelChains = request.form['parallelChains']
    new_ledSlowdown = request.form['ledSlowdown']
    new_playlistTime = request.form['playlistTime']
    new_displayTimeAndDate = request.form.get('showClockAndPicture')
    new_language = request.form.get('language')
    new_mqttIp = request.form['mqttIP']
    new_mqttPort = request.form['mqttPort']
    new_deviceId = request.form['deviceID']
    new_deviceName = request.form['deviceName']
    new_giphyApiCode = request.form['giphyApiKey']
    new_displayBrightness = request.form['displayBrightness']

    new_settings = {'heightInPixel': new_height, 'widthInPixel': new_width, 'direction': new_direction,
                    'chainLength': new_chainLength, 'parallelChains': new_parallelChains,
                    'ledSlowdown': new_ledSlowdown, 'playlistTime': new_playlistTime,
                    'displayTimeAndDate': "checked" if new_displayTimeAndDate == 'on' else "", 'language': new_language,
                    'mqttIP': new_mqttIp, 'mqttPort': new_mqttPort, 'deviceID': new_deviceId,
                    'deviceName': new_deviceName, 'giphyApiKey': new_giphyApiCode,
                    'displayBrightness': new_displayBrightness}
    save_settings(new_settings)
    return redirect(url_for('settings'))


@app.route('/process_image', methods=['POST'])
def process_image():
    image_name = request.form['image_name']
    process_thread = Thread(target=process_image_async, args=(image_name, "displayImage", app.config['STATIC_FOLDER']))
    process_thread.start()
    return redirect(url_for('index'))


@app.route('/process_demo', methods=['POST'])
def process_demo():
    demo_options = request.form['options']
    number_option = int(demo_options)
    process_thread = Thread(target=process_image_async,
                            args=(number_option, "displayDemo", app.config['STATIC_FOLDER']))
    process_thread.start()
    return redirect(url_for('index'))


@app.route('/stop_process', methods=['POST'])
def stop_process_route():
    stopProcess()
    return redirect(url_for('index'))


@app.route('/update_process', methods=['POST'])
def update_process_route():
    result = trigger_update()
    return result


@app.route('/reboot', methods=['POST'])
def reboot_route():
    result = reboot_system()
    return result


@app.route('/shutdown', methods=['POST'])
def shutdown_route():
    result = shutdown_system()
    return result


if __name__ == '__main__':
    settings = read_settings()
    mqtt_broker_ip = settings.get("mqttIP", "YOUR_MQTT_BROKER_IP")

    if mqtt_broker_ip != "YOUR_MQTT_BROKER_IP":
        mqtt_client = mqtt_handler.mqtt_listener(handle_play_media, handle_stop)
        if mqtt_client:
            mqtt_thread = Thread(target=mqtt_client.loop_forever)
            mqtt_thread.daemon = True
            mqtt_thread.start()
            mqtt_initialized = True

            # Publish discovery information
            mqtt_handler.publish_binary_sensor_discovery()
            mqtt_handler.publish_picture_count_discovery()
            mqtt_handler.publish_gif_count_discovery()
            mqtt_handler.publish_disk_space_discovery()
            # mqtt_handler.publish_device_settings_sensor_discovery()

            mqtt_handler.publish_settings_pixel_height_discovery()
            mqtt_handler.publish_settings_pixel_width_discovery()
            mqtt_handler.publish_settings_chain_length_discovery()
            mqtt_handler.publish_settings_parallel_chains_discovery()
            mqtt_handler.publish_settings_display_slowdown_discovery()
            mqtt_handler.publish_settings_display_image_in_sec_discovery()
            mqtt_handler.publish_settings_display_brightness_discovery()
            mqtt_handler.publish_device_rotation_settings_discovery()

            mqtt_handler.publish_reboot_button_discovery()
            mqtt_handler.publish_shutdown_button_discovery()
            mqtt_handler.publish_giphy_button_start_discovery()
            mqtt_handler.publish_giphy_button_stop_discovery()

            # Publish initial state
            mqtt_handler.publish_online_status()
            mqtt_handler.publish_picture_count()
            mqtt_handler.publish_gif_count()
            mqtt_handler.publish_disk_space()
            mqtt_handler.publish_device_settings_state()
            mqtt_handler.publish_device_rotation_settings_state()

            import atexit

            atexit.register(mqtt_handler.publish_offline_status)
        else:
            print("Warning: MQTT listener could not be started.")
    else:
        print("Warning: MQTT Broker IP not configured. Home Assistant discovery and control will not work.")

    upload_image(app)
    app.run(host='0.0.0.0', port=5000, debug=False)
