# modules/media_handler.py
import os
from PIL import Image

THUMBNAIL_SIZES = {
    'small': (150, 150),
    'medium': (300, 300),
    'large': (600, 600),
}

def determine_orientation(image_path):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if width > height:
                return "horizontal"
            elif height > width:
                return "vertical"
            else:
                return "square"
    except FileNotFoundError:
        return "unknown"
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return "unknown"


def get_thumbnails(static_folder, base_name):
    thumb_dir = os.path.join(static_folder, 'thumbnails')
    thumbnails = {}
    for size_name, size in THUMBNAIL_SIZES.items():
        thumb_filename = f"{base_name}_thumb_{size_name}.webp"
        thumb_path = os.path.join(thumb_dir, thumb_filename)
        if os.path.exists(thumb_path):
            thumbnails[size_name] = {
                'url': f'/static/pictures/thumbnails/{thumb_filename}',
                'width': size[0],
                'height': size[1],
            }
    return thumbnails


def get_lqip(static_folder, base_name):
    thumb_dir = os.path.join(static_folder, 'thumbnails')
    lqip_path = os.path.join(thumb_dir, f"{base_name}_lqip.txt")
    if os.path.exists(lqip_path):
        with open(lqip_path, 'r') as f:
            return f.read().strip()
    return None


def countMediaTypeAndNumber(static_folder='static/pictures'):
    image_files = os.listdir(static_folder)
    images = []
    gifs = []
    videos = []

    for file in image_files:
        image_path = os.path.join(static_folder, file)
        base_name = os.path.splitext(file)[0]
        
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            orientation = determine_orientation(image_path)
            thumbnails = get_thumbnails(static_folder, base_name)
            webp_name = base_name + '.webp'
            avif_name = base_name + '.avif'
            lqip = get_lqip(static_folder, base_name)
            images.append({
                'filename': file,
                'orientation': orientation,
                'thumbnails': thumbnails,
                'webp_url': f'/static/pictures/{webp_name}' if os.path.exists(os.path.join(static_folder, webp_name)) else None,
                'avif_url': f'/static/pictures/{avif_name}' if os.path.exists(os.path.join(static_folder, avif_name)) else None,
                'lqip': lqip,
            })
        elif file.lower().endswith('.gif'):
            orientation = determine_orientation(image_path)
            thumbnails = get_thumbnails(static_folder, base_name)
            lqip = get_lqip(static_folder, base_name)
            gifs.append({
                'filename': file,
                'orientation': orientation,
                'thumbnails': thumbnails,
                'lqip': lqip,
            })
        elif file.lower().endswith('.webm'):
            videos.append({'filename': file, 'orientation': 'horizontal'})
    return images, gifs, videos