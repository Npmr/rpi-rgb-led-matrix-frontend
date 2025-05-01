# modules/media_handler.py
import os
from PIL import Image

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

def countMediaTypeAndNumber(static_folder='static/pictures'):
    image_files = os.listdir(static_folder)
    images = []
    gifs = []
    videos = []

    for file in image_files:
        image_path = os.path.join(static_folder, file)
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            orientation = determine_orientation(image_path)
            images.append({'filename': file, 'orientation': orientation})
        elif file.lower().endswith('.gif'):
            orientation = determine_orientation(image_path)
            gifs.append({'filename': file, 'orientation': orientation})
        elif file.lower().endswith('.webm'):
            videos.append({'filename': file, 'orientation': 'horizontal'})
    return images, gifs, videos