from flask import Flask, request, redirect, url_for
import os

def upload_image(app):

  @app.route('/upload_image', methods=['POST'])
  def handle_upload():
      if 'image_file' not in request.files:
          return redirect(request.url)  # Redirect back to upload page if no file selected
      
      image_file = request.files['image_file']
      filename = image_file.filename  # Sanitize filename using werkzeug.secure_filename
      image_path = os.path.join(app.config['STATIC_FOLDER'], filename)

      try:
          image_file.save(image_path)
          return 'Image uploaded successfully!'
      except Exception as e:
          return f"Error saving image: {e}"

