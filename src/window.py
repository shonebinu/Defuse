import io
import threading

import numpy as np
import onnxruntime as ort
from gi.repository import Adw, Gio, GLib, Gtk
from PIL import Image, ImageOps


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.isnet_model_path = (
            "/app/share/io.github.shonebinu.Defuse/models/isnet-general-use.onnx"
        )
        self.onnx_session = None

        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}

        self.files_filter = Gtk.FileFilter(
            name="Image Files",
            mime_types=[f"image/{mime[1:]}" for mime in supported_extensions],
        )

    @Gtk.Template.Callback()
    def on_open_image(self, _):
        file_dialog = Gtk.FileDialog(default_filter=self.files_filter)
        file_dialog.open(self, None, self.on_image_opened)

    def on_image_opened(self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult):
        file = file_dialog.open_finish(result)
        file.load_contents_async(None, self.on_image_open_complete)

    def on_image_open_complete(self, file: Gio.File, result: Gio.AsyncResult):
        success, img_bytes, _ = file.load_contents_finish(result)

        if not success:
            raise Exception("Image could not be read.")

        threading.Thread(
            target=self.remove_bg_and_save, args=(img_bytes,), daemon=True
        ).start()

    def remove_bg_and_save(self, img_bytes: bytes):
        try:
            bg_free_img_bytes = self.remove_bg_isnet(img_bytes)

            GLib.idle_add(self.prompt_save_dialog, bg_free_img_bytes)
        except Exception as e:
            print(f"Exception: {e}")

    def remove_bg_isnet(self, img_bytes: bytes, output_format="PNG") -> bytes:
        # https://github.com/danielgatis/rembg/blob/main/rembg/sessions/dis_general_use.py

        if not self.onnx_session:
            # webgpu provider on x86 and cpu on aarch64
            self.onnx_session = ort.InferenceSession(
                self.isnet_model_path, providers=ort.get_available_providers()
            )

        img = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes)).convert("RGB"))

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

    def prompt_save_dialog(self, bg_free_img_bytes: bytes):
        file_dialog = Gtk.FileDialog(
            title="Transparent Images",
            initial_name="background_removed.png",
        )

        file_dialog.save(self, None, self.on_save_image, bg_free_img_bytes)

    def on_save_image(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, img_bytes: bytes
    ):
        file = dialog.save_finish(result)

        file.replace_contents_bytes_async(
            contents=GLib.Bytes.new(img_bytes),
            etag=None,
            make_backup=False,
            flags=Gio.FileCreateFlags.NONE,
            callback=self.on_image_save_complete,
        )

    def on_image_save_complete(self, file: Gio.File, result: Gio.AsyncResult):
        success, _ = file.replace_contents_finish(result)

        if not success:
            raise Exception("Failed to save image.")

        info = file.query_info("standard::display-name", Gio.FileQueryInfoFlags.NONE)

        display_name = (
            info.get_attribute_string("standard::display-name")
            if info
            else file.get_basename()
        )

        print(display_name)
