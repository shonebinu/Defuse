import threading

from gi.repository import Adw, Gio, GLib, Gtk


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    open_image_button: Gtk.Button = Gtk.Template.Child()
    image_file_filter: Gtk.FileFilter = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.rembg_session = None
        threading.Thread(target=self.load_rembg).start()

    def load_rembg(self):
        import onnxruntime
        import rembg

        # WebGPU for x64 and CPU for aarch64
        providers = onnxruntime.get_available_providers()

        self.rembg_session = rembg.new_session(
            model_name="isnet-general-use", providers=providers
        )
        self.rembg_module = rembg

        GLib.idle_add(self.enable_open_image_button)

    def enable_open_image_button(self):
        self.open_image_button.set_sensitive(True)

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

        image_bg_free_bytes = self.rembg_module.remove(data, session=self.rembg_session)

        file_dialog = Gtk.FileDialog(
            title="Save image",
            initial_name="untitled.png",
        )

        file_dialog.save(self, None, self.on_save_image, image_bg_free_bytes)

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
