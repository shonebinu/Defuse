import threading

from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from pathlib import Path
from .header_bar import DefuseHeaderBar
from .processor import ImageProcessor


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    navigation_view: Adw.NavigationView = Gtk.Template.Child()
    open_image_button: Gtk.Button = Gtk.Template.Child()
    picture_widget: Gtk.Picture = Gtk.Template.Child()
    buttons_stack: Gtk.Stack = Gtk.Template.Child()
    remove_bg_button: Gtk.Button = Gtk.Template.Child()
    remove_bg_spinner: Adw.Spinner = Gtk.Template.Child()
    save_bg_free_image_button: Gtk.Button = Gtk.Template.Child()

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
        self.image_file_name = Path(file.get_basename() or "").stem
        file.load_contents_async(None, self.on_image_open_complete)

    def on_image_open_complete(self, file: Gio.File, result: Gio.AsyncResult):
        success, img_bytes, _ = file.load_contents_finish(result)

        if not success:
            msg = "Could not open image"
            self.toast_overlay.add_toast(Adw.Toast(title=msg))
            return

        self.navigation_view.push_by_tag("process_page")
        self.buttons_stack.set_visible_child_name("remove_button")

        self.picture_widget.set_file(file)
        self.image_bytes = img_bytes

    def set_processing_bg(self, is_processing: bool):
        self.remove_bg_spinner.set_visible(is_processing)
        self.remove_bg_button.set_sensitive(not is_processing)

    @Gtk.Template.Callback()
    def on_remove_bg(self, _):
        self.set_processing_bg(True)

        threading.Thread(target=self.remove_bg, daemon=True).start()

    def update_ui_after_processing(self):
        self.picture_widget.set_paintable(
            Gdk.Texture.new_from_bytes(GLib.Bytes.new(self.bg_free_image_bytes))
        )
        self.set_processing_bg(False)
        self.buttons_stack.set_visible_child_name("save_button")
        self.toast_overlay.add_toast(Adw.Toast(title="Background removed"))

    def handle_process_failure(self):
        self.set_processing_bg(False)
        self.toast_overlay.add_toast(Adw.Toast(title="Could not remove background"))

    def remove_bg(self):
        try:
            self.bg_free_image_bytes = self.image_processor.remove_bg(self.image_bytes)

            GLib.idle_add(self.update_ui_after_processing)
        except Exception:
            GLib.idle_add(self.handle_process_failure)

    @Gtk.Template.Callback()
    def on_save_bg_free_image(self, _):
        self.prompt_save_dialog()

    def prompt_save_dialog(self):
        if not self.bg_free_image_bytes:
            return

        file_dialog = Gtk.FileDialog(
            initial_name=f"{self.image_file_name}_nobg.png",
        )

        file_dialog.save(self, None, self.on_save_image, self.bg_free_image_bytes)

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
            self.toast_overlay.add_toast(Adw.Toast(title="Failed to save image"))
            return

        info = file.query_info("standard::display-name", Gio.FileQueryInfoFlags.NONE)

        display_name = (
            info.get_attribute_string("standard::display-name")
            if info
            else file.get_basename()
        )

        self.toast_overlay.add_toast(Adw.Toast(title=f"Saved to {display_name}"))
