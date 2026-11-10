import os
import secrets
from functools import wraps
from flask import Flask, render_template, request, url_for, redirect, jsonify, send_from_directory, session, abort, current_app, Response
from threading import Thread
from datetime import timedelta
from PIL import Image

from upload_handler import upload_image
from modules.settings_handler import read_settings, save_settings
from modules.info_handler import read_infos
from modules.media_handler import countMediaTypeAndNumber
from modules.display_control import process_image_async, stopProcess, _current_image_name, _current_command_line, _current_static_folder, trigger_rotation, start_grid_display, stop_grid_display, is_grid_running
from modules.geometry import get_display_geometry
from modules.system_handler import getFreeDiskSpace, reboot_system, shutdown_system, sync_time, has_internet, COMMON_TIMEZONES, validate_strftime
from modules.update_handler import trigger_update, fetch_update_info
from modules.layout_handler import read_layout, save_layout, validate_layout, grid_dimensions, new_widget, WIDGET_TYPES
from modules import mqtt_handler, giphy_controller, immich_controller, immich_handler

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    print("Warning: SECRET_KEY not set in environment. Generated a random key for this session.")
app.config['STATIC_FOLDER'] = 'static/pictures'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=365).total_seconds()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Optional HTTP Basic Auth. When ADMIN_USER is set, all non-static routes
# require authentication. Disabled by default for backward compatibility.
ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')


def _check_auth(username, password):
    """Validate credentials against the configured admin user/password."""
    if not ADMIN_USER:
        return True  # authentication not configured
    return secrets.compare_digest(username or "", ADMIN_USER) and \
        secrets.compare_digest(password or "", ADMIN_PASSWORD)


def _authenticate_response():
    """Challenge the client for HTTP Basic Auth credentials."""
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Pixel Matrix"'},
    )


def _get_csrf_token():
    """Return a per-session CSRF token, creating one on first use."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


# Expose to templates so forms can render {{ csrf_token() }}
app.jinja_env.globals['csrf_token'] = _get_csrf_token


@app.before_request
def security_middleware():
    """Combined authentication + CSRF protection for all requests.

    Order matters: authentication is checked first. When the caller is
    already authenticated via HTTP Basic Auth, CSRF is skipped because
    Basic Auth already prevents cross-site request forgery.
    """
    # --- HTTP Basic Auth (only when ADMIN_USER is configured) ---
    authenticated = False
    if ADMIN_USER:
        auth = request.authorization
        authenticated = bool(auth) and _check_auth(auth.username, auth.password)
        if not authenticated and not request.path.startswith("/static/"):
            return _authenticate_response()

    # --- CSRF protection for state-changing POST requests ---
    # Skip CSRF when already authenticated via Basic Auth.
    if request.method == "POST" and not authenticated:
        token = session.get("_csrf_token")
        request_token = (
            request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        )
        if not token or not request_token or not secrets.compare_digest(token, request_token):
            abort(403, description="CSRF token missing or invalid")


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
    settings_data = read_settings()
    free_gb = freeDiskSpaceInPercent[1]
    return render_template('upload.html', freeDiskSpaceInPercent=round(freeDiskSpaceInPercent[0]),
                           freeDiskSpace=f"{free_gb} GB", settings=settings_data)


def _is_safe_filename(filename):
    """Reject filenames that could escape the static folder via path traversal."""
    if not filename:
        return False
    # Reject path separators and traversal sequences
    if '/' in filename or '\\' in filename or '..' in filename:
        return False
    # Only allow a basename
    return os.path.basename(filename) == filename


@app.route('/delete_image', methods=['POST'])
def delete_image():
    image_name = request.form.get('image_name_to_delete', '')
    if not _is_safe_filename(image_name):
        return redirect(url_for('index'))
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
                           enableUpdateButton=enableUpdateButton, timezones=COMMON_TIMEZONES)


@app.route('/layout')
def layout():
    settings_data = read_settings()
    geometry = get_display_geometry(settings_data)
    layout_data = read_layout()
    cols, rows, cell_w, cell_h = grid_dimensions(geometry)

    pictures = []
    static_folder = app.config['STATIC_FOLDER']
    if os.path.isdir(static_folder):
        pictures = sorted(
            name for name in os.listdir(static_folder)
            if name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))
        )

    widget_defaults = {widget_type: new_widget(widget_type) for widget_type in WIDGET_TYPES}

    return render_template(
        'layout.html',
        layout=layout_data,
        settings=settings_data,
        matrixWidth=geometry['width'],
        matrixHeight=geometry['height'],
        cols=cols,
        rows=rows,
        cellW=cell_w,
        cellH=cell_h,
        pictures=pictures,
        widgetDefaults=widget_defaults,
        widgetTypes=WIDGET_TYPES,
        gridRunning=is_grid_running(),
    )


@app.route('/save_layout', methods=['POST'])
def save_layout_route():
    settings_data = read_settings()
    geometry = get_display_geometry(settings_data)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'errors': ['Invalid layout payload']}), 400

    normalized, errors = validate_layout(payload, geometry)
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    if not save_layout(normalized):
        return jsonify({'ok': False, 'errors': ['Could not write layout.json']}), 500

    return jsonify({'ok': True, 'layout': normalized})


@app.route('/start_grid', methods=['POST'])
def start_grid():
    start_grid_display()
    return redirect(url_for('layout'))


@app.route('/stop_grid', methods=['POST'])
def stop_grid():
    stop_grid_display()
    return redirect(url_for('layout'))


@app.route('/changelog')
def changelog():
    infos = read_infos()
    changelog = infos.get('changelog', [])
    current_version = infos.get('currentApplicationVersion', 'unknown')
    settings_data = read_settings()
    update_branch = settings_data.get('updateBranch', 'main')
    update_info = fetch_update_info(update_branch)
    update_version = update_info.get('currentApplicationVersion') if update_info else 'unknown'
    current_version_num = infos.get('currentApplicationVersion', 'unknown')
    enable_update_button = "" if update_version != current_version_num and update_info else "disabled"
    return render_template('changelog.html', changelog=changelog, current_version=current_version,
                           applicationInfo=infos, settings=settings_data,
                           currentAvailableVersion=update_version, enableUpdateButton=enable_update_button)


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
    new_immichAutoOrientation = request.form.get('immichAutoOrientation', 'true')
    new_timezone = request.form.get('timezone', 'UTC')
    new_clockFormatDate = request.form.get('clockFormatDate', '%A')
    new_clockFormatTime = request.form.get('clockFormatTime', '%H:%M:%S')

    # Validate strftime formats
    valid, err = validate_strftime(new_clockFormatDate)
    if not valid:
        return f"Invalid date format: {err}", 400
    valid, err = validate_strftime(new_clockFormatTime)
    if not valid:
        return f"Invalid time format: {err}", 400

    # Merge form values into existing settings so keys not present in the form
    # (e.g. custom or future settings) are preserved instead of being deleted.
    existing_settings = read_settings()
    merged_settings = {
        'heightInPixel': new_height,
        'widthInPixel': new_width,
        'direction': new_direction if new_direction else existing_settings.get('direction', 'horizontal'),
        'chainLength': new_chainLength,
        'parallelChains': new_parallelChains,
        'ledSlowdown': new_ledSlowdown,
        'playlistTime': new_playlistTime,
        'displayTimeAndDate': "checked" if new_displayTimeAndDate == 'on' else "",
        'language': new_language,
        'mqttIP': new_mqttIp,
        'mqttPort': new_mqttPort,
        'deviceID': new_deviceId,
        'deviceName': new_deviceName,
        'giphyApiKey': new_giphyApiCode,
        'displayBrightness': new_displayBrightness,
        'webpQuality': new_webpQuality,
        'avifQuality': new_avifQuality,
        'thumbnailQuality': new_thumbnailQuality,
        'updateBranch': new_updateBranch,
        'immichUrl': new_immichUrl,
        'immichApiKey': new_immichApiKey,
        'immichAlbumId': new_immichAlbumId,
        'immichSearchQuery': new_immichSearchQuery,
        'immichDisplayDurationRandom': new_immichDisplayDurationRandom,
        'immichDisplayDurationAlbum': new_immichDisplayDurationAlbum,
        'immichDisplayDurationSearch': new_immichDisplayDurationSearch,
        'immichAutoOrientation': new_immichAutoOrientation,
        'timezone': new_timezone,
        'clockFormatDate': new_clockFormatDate,
        'clockFormatTime': new_clockFormatTime,
    }
    existing_settings.update(merged_settings)
    save_settings(existing_settings)
    return redirect(url_for('settings'))


@app.route('/sync_time', methods=['POST'])
def sync_time_route():
    return sync_time()


@app.route('/regenerate_thumbnails', methods=['POST'])
def regenerate_thumbnails():
    from upload_handler import generate_thumbnails, convert_to_webp, convert_to_avif, generate_lqip, get_image_metadata
    static_folder = app.config['STATIC_FOLDER']
    thumb_dir = os.path.join(static_folder, 'thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)

    if not os.path.isdir(static_folder):
        return jsonify({'regenerated': [], 'errors': [f"Static folder '{static_folder}' not found"]})

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
    # Extract EXIF orientation from the image file
    exif_orientation = None
    image_path = os.path.join(app.config['STATIC_FOLDER'], image_name)
    if os.path.exists(image_path):
        try:
            with Image.open(image_path) as img:
                exif = img.getexif()
                if exif:
                    exif_orientation = exif.get(0x0112)  # Orientation tag
        except Exception as e:
            print(f"Error reading EXIF orientation from {image_name}: {e}")
    
    process_thread = Thread(target=process_image_async, args=(image_name, "displayImage", app.config['STATIC_FOLDER'], None, exif_orientation))
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
    immich_controller.stop_immich_loop()
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

    # Non-blocking NTP time sync at startup if internet is available
    if has_internet():
        print("Internet available - syncing time (non-blocking)...")
        sync_time()
    else:
        print("No internet detected - skipping time sync")

    app.run(host='0.0.0.0', port=5000, debug=False)
