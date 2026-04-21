import threading

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .header_bar import DefuseHeaderBar
from .processor import ImageProcessor


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    navigation_view: Adw.NavigationView = Gtk.Template.Child()
    open_image_button: Gtk.Button = Gtk.Template.Child()
    picture_widget: Gtk.Picture = Gtk.Template.Child()
    process_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.image_processor = ImageProcessor()

        self.files_filter = Gtk.FileFilter(
            name="Image Files",
            mime_types=self.image_processor.get_supported_mimes(),
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

        self.navigation_view.push_by_tag("process_page")
        self.picture_widget.set_file(file)

        # threading.Thread(
        #     target=self.remove_bg_and_save, args=(img_bytes,), daemon=True
        # ).start()

    def remove_bg_and_save(self, img_bytes: bytes):
        try:
            bg_free_img_bytes = self.image_processor.remove_bg(img_bytes)

            GLib.idle_add(self.prompt_save_dialog, bg_free_img_bytes)
        except Exception as e:
            print(f"Exception: {e}")

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
