import os
import io
import base64
from flask import request, redirect, jsonify
from PIL import Image

THUMBNAIL_SIZES = {
    'small': (150, 150),
    'medium': (300, 300),
    'large': (600, 600),
}
LQIP_SIZE = (20, 20)

DEFAULT_WEBP_QUALITY = 85
DEFAULT_AVIF_QUALITY = 50
DEFAULT_THUMBNAIL_QUALITY = 80

def get_quality_settings():
    try:
        import json
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        settings_path = os.path.join(project_root, 'settings.json')
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        return {
            'webp_quality': settings.get('webpQuality', DEFAULT_WEBP_QUALITY),
            'avif_quality': settings.get('avifQuality', DEFAULT_AVIF_QUALITY),
            'thumbnail_quality': settings.get('thumbnailQuality', DEFAULT_THUMBNAIL_QUALITY),
        }
    except Exception:
        return {
            'webp_quality': DEFAULT_WEBP_QUALITY,
            'avif_quality': DEFAULT_AVIF_QUALITY,
            'thumbnail_quality': DEFAULT_THUMBNAIL_QUALITY,
        }

def generate_lqip(image_data):
    try:
        img = Image.open(io.BytesIO(image_data))
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        img.thumbnail(LQIP_SIZE, Image.Resampling.LANCZOS)
        img = img.filter(Image.Filter.GaussianBlur(radius=2))
        
        buffer = io.BytesIO()
        img.save(buffer, format='WEBP', quality=20)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error generating LQIP: {e}")
        return None


def generate_thumbnails(image_data, filename):
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        quality_settings = get_quality_settings()
        thumbnail_quality = quality_settings['thumbnail_quality']
        
        thumbnails = {}
        for size_name, size in THUMBNAIL_SIZES.items():
            thumb_img = img.copy()
            thumb_img.thumbnail(size, Image.Resampling.LANCZOS)
            
            thumb_buffer = io.BytesIO()
            thumb_img.save(thumb_buffer, format='WEBP', quality=thumbnail_quality, method=6)
            thumb_buffer.seek(0)
            
            thumb_filename = f"{os.path.splitext(filename)[0]}_thumb_{size_name}.webp"
            thumbnails[size_name] = {
                'filename': thumb_filename,
                'data': thumb_buffer.getvalue(),
                'width': thumb_img.width,
                'height': thumb_img.height,
            }
        
        return thumbnails
    except Exception as e:
        print(f"Error generating thumbnails for {filename}: {e}")
        return {}


def convert_to_webp(image_data, filename):
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        quality_settings = get_quality_settings()
        webp_quality = quality_settings['webp_quality']
        
        webp_buffer = io.BytesIO()
        img.save(webp_buffer, format='WEBP', quality=webp_quality, method=6)
        webp_buffer.seek(0)
        
        webp_filename = os.path.splitext(filename)[0] + '.webp'
        return webp_filename, webp_buffer.getvalue()
    except Exception as e:
        print(f"Error converting {filename} to WebP: {e}")
        return None, None


def convert_to_avif(image_data, filename):
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        quality_settings = get_quality_settings()
        avif_quality = quality_settings['avif_quality']
        
        avif_buffer = io.BytesIO()
        img.save(avif_buffer, format='AVIF', quality=avif_quality)
        avif_buffer.seek(0)
        
        avif_filename = os.path.splitext(filename)[0] + '.avif'
        return avif_filename, avif_buffer.getvalue()
    except Exception as e:
        print(f"Error converting {filename} to AVIF: {e}")
        return None, None

def get_image_metadata(image_data):
    try:
        img = Image.open(io.BytesIO(image_data))
        return {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode,
            'orientation': 'horizontal' if img.width > img.height else 'vertical' if img.height > img.width else 'square'
        }
    except Exception as e:
        print(f"Error getting metadata: {e}")
        return None

def upload_image(app):
    @app.route('/upload_image', methods=['POST'])
    def handle_upload():
        if 'image_file' not in request.files:
            return redirect(request.url)

        images = request.files.getlist('image_file')
        uploaded = []
        errors = []

        for image in images:
            if image.filename == '':
                continue
            
            filename = image.filename
            image_data = image.read()
            
            if not image_data:
                errors.append(f"{filename}: Empty file")
                continue
            
            metadata = get_image_metadata(image_data)
            if not metadata:
                errors.append(f"{filename}: Invalid image format")
                continue
            
            image_path = os.path.join(app.config['STATIC_FOLDER'], filename)
            thumb_dir = os.path.join(app.config['STATIC_FOLDER'], 'thumbnails')
            os.makedirs(thumb_dir, exist_ok=True)
            
            try:
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                
                thumbnails = generate_thumbnails(image_data, filename)
                for size_name, thumb_info in thumbnails.items():
                    thumb_path = os.path.join(thumb_dir, thumb_info['filename'])
                    with open(thumb_path, 'wb') as f:
                        f.write(thumb_info['data'])
                
                lqip_base64 = generate_lqip(image_data)
                
                webp_filename, webp_data = convert_to_webp(image_data, filename)
                if webp_filename and webp_data:
                    webp_path = os.path.join(app.config['STATIC_FOLDER'], webp_filename)
                    with open(webp_path, 'wb') as f:
                        f.write(webp_data)
                
                avif_filename, avif_data = convert_to_avif(image_data, filename)
                if avif_filename and avif_data:
                    avif_path = os.path.join(app.config['STATIC_FOLDER'], avif_filename)
                    with open(avif_path, 'wb') as f:
                        f.write(avif_data)
                
                uploaded.append({
                    'filename': filename,
                    'webp_filename': webp_filename,
                    'avif_filename': avif_filename,
                    'thumbnails': {k: v['filename'] for k, v in thumbnails.items()},
                    'lqip': lqip_base64,
                    'metadata': metadata
                })
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
                if os.path.exists(image_path):
                    os.remove(image_path)

        if errors:
            return jsonify({'success': len(uploaded), 'errors': errors}), 207 if uploaded else 400
        return jsonify({'success': len(uploaded), 'uploaded': uploaded})

    @app.route('/api/images/metadata', methods=['GET'])
    def get_images_metadata():
        static_folder = app.config['STATIC_FOLDER']
        thumb_dir = os.path.join(static_folder, 'thumbnails')
        image_files = os.listdir(static_folder)
        images = []
        
        for file in image_files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.webm', '.avif')):
                file_path = os.path.join(static_folder, file)
                try:
                    with open(file_path, 'rb') as f:
                        metadata = get_image_metadata(f.read())
                    if metadata:
                        base_name = os.path.splitext(file)[0]
                        thumbnails = {}
                        for size_name in THUMBNAIL_SIZES.keys():
                            thumb_filename = f"{base_name}_thumb_{size_name}.webp"
                            thumb_path = os.path.join(thumb_dir, thumb_filename)
                            if os.path.exists(thumb_path):
                                thumbnails[size_name] = {
                                    'url': f'/static/pictures/thumbnails/{thumb_filename}',
                                    'width': THUMBNAIL_SIZES[size_name][0],
                                    'height': THUMBNAIL_SIZES[size_name][1],
                                }
                        
                        webp_path = os.path.join(static_folder, base_name + '.webp')
                        avif_path = os.path.join(static_folder, base_name + '.avif')
                        
                        lqip_path = os.path.join(thumb_dir, f"{base_name}_lqip.txt")
                        lqip = None
                        if os.path.exists(lqip_path):
                            with open(lqip_path, 'r') as f:
                                lqip = f.read().strip()
                        
                        images.append({
                            'filename': file,
                            'metadata': metadata,
                            'thumbnails': thumbnails,
                            'has_webp': os.path.exists(webp_path),
                            'has_avif': os.path.exists(avif_path),
                            'webp_url': f'/static/pictures/{base_name}.webp' if os.path.exists(webp_path) else None,
                            'avif_url': f'/static/pictures/{base_name}.avif' if os.path.exists(avif_path) else None,
                            'lqip': lqip,
                        })
                except Exception as e:
                    print(f"Error reading {file}: {e}")
        
        return jsonify(images)

    @app.route('/api/image/<filename>/thumbnail', methods=['GET'])
    def get_thumbnail(filename):
        size = request.args.get('size', 'medium')
        if size not in THUMBNAIL_SIZES:
            size = 'medium'
        
        thumb_dir = os.path.join(app.config['STATIC_FOLDER'], 'thumbnails')
        base_name = os.path.splitext(filename)[0]
        thumb_filename = f"{base_name}_thumb_{size}.webp"
        thumb_path = os.path.join(thumb_dir, thumb_filename)
        
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype='image/webp')
        
        file_path = os.path.join(app.config['STATIC_FOLDER'], filename)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                image_data = f.read()
            thumbnails = generate_thumbnails(image_data, filename)
            if size in thumbnails:
                os.makedirs(thumb_dir, exist_ok=True)
                thumb_data = thumbnails[size]['data']
                with open(thumb_path, 'wb') as f:
                    f.write(thumb_data)
                return send_file(thumb_path, mimetype='image/webp')
        
        return '', 404

    @app.route('/api/image/<filename>/lqip', methods=['GET'])
    def get_lqip(filename):
        thumb_dir = os.path.join(app.config['STATIC_FOLDER'], 'thumbnails')
        base_name = os.path.splitext(filename)[0]
        lqip_path = os.path.join(thumb_dir, f"{base_name}_lqip.txt")
        
        if os.path.exists(lqip_path):
            with open(lqip_path, 'r') as f:
                lqip = f.read().strip()
            return jsonify({'lqip': lqip})
        
        file_path = os.path.join(app.config['STATIC_FOLDER'], filename)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                image_data = f.read()
            lqip = generate_lqip(image_data)
            if lqip:
                os.makedirs(thumb_dir, exist_ok=True)
                with open(lqip_path, 'w') as f:
                    f.write(lqip)
                return jsonify({'lqip': lqip})
        
        return jsonify({'lqip': None}), 404

    from flask import send_file