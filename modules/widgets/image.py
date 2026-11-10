# modules/widgets/image.py
"""Image/picture widget that renders a file into its grid cells."""
import os

from PIL import Image

from .base import Widget


def _is_safe_filename(filename):
    if not filename:
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return os.path.basename(filename) == filename


class ImageWidget(Widget):
    type_id = "image"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.filename = self.config.get("filename", "")
        self.fit = self.style.get("fit", "cover")
        self._image = None
        self._mtime = None

    def _path(self):
        if not _is_safe_filename(self.filename):
            return None
        return os.path.join(self.context.static_pictures_dir, self.filename)

    def _ensure_image(self):
        path = self._path()
        if not path:
            return None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        if self._image is None or mtime != self._mtime:
            try:
                with Image.open(path) as opened:
                    self._image = opened.convert("RGB")
                self._mtime = mtime
            except (OSError, ValueError) as error:
                print(f"Image widget: could not load {path}: {error}")
                self._image = None
                self._mtime = None
        return self._image

    def render(self, surface, rect):
        x, y, w, h = rect
        image = self._ensure_image()
        if image is None:
            return
        surface.draw_image(image, x, y, w, h, fit=self.fit)

    def stop(self):
        self._image = None
