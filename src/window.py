import io
import threading

import numpy as np
import onnxruntime as ort
from gi.repository import Adw, Gio, GLib, Gtk
from PIL import Image, ImageOps


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    image_file_filter: Gtk.FileFilter = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        isnet_model_path = (
            "/app/share/io.github.shonebinu.Defuse/models/isnet-general-use.onnx"
        )

        # webgpu provider on x86 and cpu on aarch64
        self.onnx_session = ort.InferenceSession(
            isnet_model_path, providers=ort.get_available_providers()
        )

        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

        print(supported_extensions)

    @Gtk.Template.Callback()
    def on_open_image(self, _):
        file_dialog = Gtk.FileDialog(default_filter=self.image_file_filter)
        file_dialog.open(self, None, self.on_image_opened)

    def on_image_opened(self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult):
        file = file_dialog.open_finish(result)
        file.load_contents_async(None, self.on_image_open_complete)

    def on_image_open_complete(self, file: Gio.File, result: Gio.AsyncResult):
        success, data, _ = file.load_contents_finish(result)

        if not success:
            raise Exception("Image could not be read.")

        image_bg_free_bytes = self.remove_bg_isnet(data)

        file_dialog = Gtk.FileDialog(
            title="Save image",
            initial_name="untitled.png",
        )

        file_dialog.save(self, None, self.on_save_image, image_bg_free_bytes)

    def remove_bg_isnet(self, image_bytes: bytes, output_format="PNG") -> bytes:
        # https://github.com/danielgatis/rembg/blob/main/rembg/sessions/dis_general_use.py

        img = ImageOps.exif_transpose(
            Image.open(io.BytesIO(image_bytes)).convert("RGB")
        )

        mean, std, size = 0.5, 1.0, (1024, 1024)

        arr = np.array(img.resize(size, Image.Resampling.LANCZOS)).astype(np.float32)
        img_input = ((arr / max(arr.max(), 1e-6) - mean) / std).transpose(2, 0, 1)

        out = self.onnx_session.run(
            None, {self.onnx_session.get_inputs()[0].name: img_input[None]}
        )[0][0, 0]  # type: ignore

        ma, mi = out.max(), out.min()
        mask = Image.fromarray(
            ((out - mi) / max((ma - mi), 1e-6) * 255).astype("uint8"), "L"
        ).resize(img.size, Image.Resampling.LANCZOS)

        bio = io.BytesIO()
        Image.composite(img.convert("RGBA"), Image.new("RGBA", img.size, 0), mask).save(
            bio, format=output_format
        )
        return bio.getvalue()

    def on_save_image(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, image_bytes: bytes
    ):
        file = dialog.save_finish(result)

        file.replace_contents_bytes_async(
            contents=GLib.Bytes.new(image_bytes),
            etag=None,
            make_backup=False,
            flags=Gio.FileCreateFlags.NONE,
            callback=self.on_image_save_complete,
        )

    def on_image_save_complete(self, file: Gio.File, result: Gio.AsyncResult):
        success, _ = file.replace_contents_finish(result)

        info = file.query_info("standard::display-name", Gio.FileQueryInfoFlags.NONE)

        display_name = (
            info.get_attribute_string("standard::display-name")
            if info
            else file.get_basename()
        )

        print(display_name)
