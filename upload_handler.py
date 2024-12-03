import os

from flask import request, redirect


def upload_image(app):
    @app.route('/upload_image', methods=['POST'])
    def handle_upload():
        if 'image_file' not in request.files:  # Check for 'images' instead of 'image_file'
            return redirect(request.url)  # Redirect back if no files selected

        images = request.files.getlist('image_file')  # Get a list of uploaded files

        # Loop through each uploaded image
        for image in images:
            if image.filename == '':
                return 'No selected file'
            filename = image.filename  # Sanitize filename
            image_path = os.path.join(app.config['STATIC_FOLDER'], filename)

            try:
                image.save(image_path)
            except Exception as e:
                return f"Error saving image {filename}: {e}"

        return f'{len(images)} images uploaded successfully!'  # Return success message with number of images
