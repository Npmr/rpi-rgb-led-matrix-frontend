import os
from flask import Flask, render_template, request, url_for, redirect, jsonify, send_from_directory
from threading import Thread
from datetime import timedelta

from upload_handler import upload_image
from modules.settings_handler import read_settings, save_settings
from modules.info_handler import read_infos
from modules.media_handler import countMediaTypeAndNumber
from modules.display_control import process_image_async, stopProcess, trigger_rotation, set_brightness, update_display_settings, start_text_scroll, stop_text_scroll, get_display_controller, start_text_scroll, stop_text_scroll
from modules.system_handler import getFreeDiskSpace, reboot_system, shutdown_system
from modules.update_handler import trigger_update, fetch_update_info
from modules import mqtt_handler, giphy_controller, immich_controller, immich_handler

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['STATIC_FOLDER'] = 'static/pictures'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=365).total_seconds()


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
        thumb_dir = os.path.join(app.config['STATIC_FOLDER'], 'thumbnails')
        base_name = os.path.splitext(image_name)[0]
        for size_name in ['small', 'medium', 'large']:
            thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb_{size_name}.webp")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        lqip_path = os.path.join(thumb_dir, f"{base_name}_lqip.txt")
        if os.path.exists(lqip_path):
            os.remove(lqip_path)
        webp_path = os.path.join(app.config['STATIC_FOLDER'], base_name + '.webp')
        if os.path.exists(webp_path):
            os.remove(webp_path)
        avif_path = os.path.join(app.config['STATIC_FOLDER'], base_name + '.avif')
        if os.path.exists(avif_path):
            os.remove(avif_path)
        return redirect(url_for('index'))
    except OSError as e:
        return redirect(url_for('index'))


@app.route('/static/pictures/<path:filename>')
def serve_picture(filename):
    response = send_from_directory(app.config['STATIC_FOLDER'], filename)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@app.route('/static/pictures/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    thumb_dir = os.path.join(app.config['STATIC_FOLDER'], 'thumbnails')
    response = send_from_directory(thumb_dir, filename)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


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


@app.route('/start_immich_random', methods=['POST'])
def start_immich_random():
    print("Web request received to start Immich random")
    immich_controller.start_immich_loop("random")
    return redirect(url_for('index'))


@app.route('/start_immich_album', methods=['POST'])
def start_immich_album():
    album_id = request.form.get('immich_album_id')
    if album_id:
        print(f"Web request received to start Immich album: {album_id}")
        immich_controller.start_immich_loop("album", album_id=album_id)
        return redirect(url_for('index'))
    else:
        return "Error: No album selected.", 400


@app.route('/start_immich_search', methods=['POST'])
def start_immich_search():
    query = request.form.get('immich_search_query')
    if query:
        print(f"Web request received to start Immich search: {query}")
        immich_controller.start_immich_loop("search", search_query=query)
        return redirect(url_for('index'))
    else:
        return "Error: No search query provided.", 400


@app.route('/stop_immich', methods=['POST'])
def stop_immich():
    print("Web request received to stop Immich")
    immich_controller.stop_immich_loop()
    return redirect(url_for('index'))


@app.route('/get_immich_albums')
def get_immich_albums():
    albums = immich_handler.get_albums()
    return jsonify(albums)


# Text Scroll API routes
@app.route('/api/text_scroll/start', methods=['POST'])
def start_text_scroll_api():
    data = request.get_json() or request.form
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    font = data.get('font')
    text_color = data.get('text_color', [255, 255, 255])
    bg_color = data.get('bg_color', [0, 0, 0])
    speed = float(data.get('speed', 0.05))
    y_pos = int(data.get('y_pos', 10))
    loop = data.get('loop', True)
    blink_on = int(data.get('blink_on', 0))
    blink_off = int(data.get('blink_off', 0))
    
    # Convert color lists to tuples
    if isinstance(text_color, list):
        text_color = tuple(text_color)
    if isinstance(bg_color, list):
        bg_color = tuple(bg_color)
    
    start_text_scroll(text, font=font, text_color=text_color, bg_color=bg_color,
                      speed=speed, y_pos=y_pos, loop=loop, blink_on=blink_on, blink_off=blink_off)
    
    return jsonify({'status': 'started', 'text': text})


@app.route('/api/text_scroll/stop', methods=['POST'])
def stop_text_scroll_api():
    stop_text_scroll()
    return jsonify({'status': 'stopped'})


@app.route('/api/text_scroll/status')
def text_scroll_status():
    controller = get_display_controller()
    if controller._text_scroller and controller._text_scroller.is_running():
        return jsonify({'running': True, 'text': controller._current_task[1] if controller._current_task and controller._current_task[0] == 'text_scroll' else ''})
    return jsonify({'running': False})


@app.route('/settings')
def settings():
    settings = read_settings()
    medias = countMediaTypeAndNumber(app.config['STATIC_FOLDER'])
    numberOfPictues = len(medias[0])
    numberOfGifs = len(medias[1])
    freeDiskSpaceInPercent = getFreeDiskSpace()
    infos = read_infos()
    update_branch = settings.get('updateBranch', 'main')
    update_info = fetch_update_info(update_branch)

    updateVersion = update_info.get('currentApplicationVersion') if update_info else 'unknown'
    updateText = update_info.get('whatChanged') if update_info else ''
    currentVersion = infos.get('currentApplicationVersion', 'unknown')

    enableUpdateButton = "" if updateVersion != currentVersion and update_info else "disabled"

    return render_template('settings.html', settings=settings, numberOfPictues=numberOfPictues,
                           numberOfGifs=numberOfGifs, freeDiskSpaceInPercent=round(freeDiskSpaceInPercent[0]),
                           applicationInfo=infos, updateText=updateText, currentAvailableVersion=updateVersion,
                           enableUpdateButton=enableUpdateButton)


@app.route('/changelog')
def changelog():
    infos = read_infos()
    changelog = infos.get('changelog', [])
    current_version = infos.get('currentApplicationVersion', 'unknown')
    return render_template('changelog.html', changelog=changelog, current_version=current_version, applicationInfo=infos)


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
    new_webpQuality = request.form.get('webpQuality', '85')
    new_avifQuality = request.form.get('avifQuality', '50')
    new_thumbnailQuality = request.form.get('thumbnailQuality', '80')
    new_updateBranch = request.form.get('updateBranch', 'main')
    new_immichUrl = request.form.get('immichUrl', '')
    new_immichApiKey = request.form.get('immichApiKey', '')
    new_immichAlbumId = request.form.get('immichAlbumId', '')
    new_immichSearchQuery = request.form.get('immichSearchQuery', '')
    new_immichDisplayDurationRandom = request.form.get('immichDisplayDurationRandom', '30')
    new_immichDisplayDurationAlbum = request.form.get('immichDisplayDurationAlbum', '30')
    new_immichDisplayDurationSearch = request.form.get('immichDisplayDurationSearch', '30')

    new_settings = {'heightInPixel': new_height, 'widthInPixel': new_width, 'direction': new_direction,
                    'chainLength': new_chainLength, 'parallelChains': new_parallelChains,
                    'ledSlowdown': new_ledSlowdown, 'playlistTime': new_playlistTime,
                    'displayTimeAndDate': "checked" if new_displayTimeAndDate == 'on' else "", 'language': new_language,
                    'mqttIP': new_mqttIp, 'mqttPort': new_mqttPort, 'deviceID': new_deviceId,
                    'deviceName': new_deviceName, 'giphyApiKey': new_giphyApiCode,
                    'displayBrightness': new_displayBrightness,
                    'webpQuality': new_webpQuality, 'avifQuality': new_avifQuality,
                    'thumbnailQuality': new_thumbnailQuality,
                    'updateBranch': new_updateBranch,
                    'immichUrl': new_immichUrl, 'immichApiKey': new_immichApiKey,
                    'immichAlbumId': new_immichAlbumId, 'immichSearchQuery': new_immichSearchQuery,
                    'immichDisplayDurationRandom': new_immichDisplayDurationRandom,
                    'immichDisplayDurationAlbum': new_immichDisplayDurationAlbum,
                    'immichDisplayDurationSearch': new_immichDisplayDurationSearch}
    save_settings(new_settings)
    return redirect(url_for('settings'))


@app.route('/regenerate_thumbnails', methods=['POST'])
def regenerate_thumbnails():
    from upload_handler import generate_thumbnails, convert_to_webp, convert_to_avif, generate_lqip, get_image_metadata
    static_folder = app.config['STATIC_FOLDER']
    thumb_dir = os.path.join(static_folder, 'thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)
    
    image_files = os.listdir(static_folder)
    regenerated = []
    errors = []
    
    for file in image_files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            file_path = os.path.join(static_folder, file)
            try:
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                base_name = os.path.splitext(file)[0]
                
                thumbnails = generate_thumbnails(image_data, file)
                for size_name, thumb_info in thumbnails.items():
                    thumb_path = os.path.join(thumb_dir, thumb_info['filename'])
                    with open(thumb_path, 'wb') as f:
                        f.write(thumb_info['data'])
                
                lqip_base64 = generate_lqip(image_data)
                if lqip_base64:
                    lqip_path = os.path.join(thumb_dir, f"{base_name}_lqip.txt")
                    with open(lqip_path, 'w') as f:
                        f.write(lqip_base64)
                
                webp_filename, webp_data = convert_to_webp(image_data, file)
                if webp_filename and webp_data:
                    webp_path = os.path.join(static_folder, webp_filename)
                    with open(webp_path, 'wb') as f:
                        f.write(webp_data)
                
                avif_filename, avif_data = convert_to_avif(image_data, file)
                if avif_filename and avif_data:
                    avif_path = os.path.join(static_folder, avif_filename)
                    with open(avif_path, 'wb') as f:
                        f.write(avif_data)
                
                regenerated.append(file)
            except Exception as e:
                errors.append(f"{file}: {str(e)}")
    
    return jsonify({'regenerated': regenerated, 'errors': errors})


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


@app.route('/rotate_left', methods=['POST'])
def rotate_left():
    trigger_rotation(-90)
    return redirect(url_for('index'))

@app.route('/rotate_right', methods=['POST'])
def rotate_right():
    trigger_rotation(90)
    return redirect(url_for('index'))


@app.route('/update_process', methods=['POST'])
def update_process_route():
    settings = read_settings()
    update_branch = settings.get('updateBranch', 'main')
    result = trigger_update(update_branch)
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
            
            mqtt_handler.publish_text_scroll_start_discovery()
            mqtt_handler.publish_text_scroll_stop_discovery()

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
