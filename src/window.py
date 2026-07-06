import threading
from typing import Literal
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from pathlib import Path
from .header_bar import DefuseHeaderBar
from .processor import ImageProcessor


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    drag_revealer: Gtk.Revealer = Gtk.Template.Child()
    navigation_view: Adw.NavigationView = Gtk.Template.Child()
    open_image_button: Gtk.Button = Gtk.Template.Child()
    process_stack: Adw.ViewStack = Gtk.Template.Child()
    picture_widget: Gtk.Picture = Gtk.Template.Child()
    buttons_stack: Adw.ViewStack = Gtk.Template.Child()
    remove_bg_button: Gtk.Button = Gtk.Template.Child()
    remove_bg_spinner: Adw.Spinner = Gtk.Template.Child()
    save_bg_free_image_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.image_processor = ImageProcessor()
        self.is_busy = False

        self.supported_mimes = self.image_processor.get_supported_mimes()
        self.files_filter = Gtk.FileFilter(
            name="Image Files",
            mime_types=self.supported_mimes,
        )

    @Gtk.Template.Callback()
    def on_image_enter(self, *_) -> Literal[Gdk.DragAction.COPY]:
        self.drag_revealer.set_reveal_child(True)
        self.navigation_view.add_css_class("blurred")
        return Gdk.DragAction.COPY

    @Gtk.Template.Callback()
    def on_image_leave(self, *_):
        self.drag_revealer.set_reveal_child(False)
        self.navigation_view.remove_css_class("blurred")

    @Gtk.Template.Callback()
    def on_image_drop(
        self,
        _,
        contents: Gdk.FileList | Gdk.Texture,
        *args,
    ):
        if self.is_busy:
            self.toast_overlay.add_toast(
                Adw.Toast(title="Please wait for the current process to finish")
            )
            return

        if isinstance(contents, Gdk.FileList):
            if len(contents) > 1:
                self.toast_overlay.add_toast(
                    Adw.Toast(title="Only one file can be processed at once")
                )
                return

            file = contents.get_files()[0]
            info = file.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                Gio.FileQueryInfoFlags.NONE,
            )

            mime_type = info.get_content_type()

            if not mime_type or mime_type not in self.supported_mimes:
                self.toast_overlay.add_toast(
                    Adw.Toast(
                        title=f"Unsupported file format{': ' + mime_type if mime_type else ''}"
                    )
                )
                return

            self.on_load_image(file)
        elif isinstance(contents, Gdk.Texture):
            self.show_loading_page()
            self.is_busy = True

            threading.Thread(
                target=self.process_dropped_texture, daemon=True, args=(contents,)
            ).start()

    @Gtk.Template.Callback()
    def on_open_image(self, _):
        if self.is_busy:
            return

        file_dialog = Gtk.FileDialog(default_filter=self.files_filter)
        file_dialog.open(self, None, self.on_image_opened)

    @Gtk.Template.Callback()
    def on_remove_bg(self, _):
        self.set_processing_bg(True)

        threading.Thread(target=self.remove_bg, daemon=True).start()

    @Gtk.Template.Callback()
    def on_save_bg_free_image(self, _):
        self.prompt_save_dialog()

    def on_image_opened(self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult):
        file = file_dialog.open_finish(result)
        self.on_load_image(file)

    def on_load_image(self, file: Gio.File):
        self.show_loading_page()
        self.is_busy = True
        file.load_contents_async(None, self.on_image_loaded)

    def on_image_loaded(self, file: Gio.File, result: Gio.AsyncResult):
        success, img_bytes, _ = file.load_contents_finish(result)

        if not success:
            self.handle_load_failure("Could not open image")
            return

        display_name = Path(file.get_basename() or "image").stem

        threading.Thread(
            target=self.prepare_image_data,
            args=(img_bytes, display_name),
            daemon=True,
        ).start()

    def process_dropped_texture(self, texture: Gdk.Texture):
        if not (img_bytes := texture.save_to_png_bytes().get_data()):
            GLib.idle_add(self.handle_load_failure)
            return

        GLib.idle_add(self.prepare_for_processing, img_bytes, "dropped_image", texture)

    def prepare_image_data(self, img_bytes: bytes, display_name: str):
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(img_bytes))

        GLib.idle_add(self.prepare_for_processing, img_bytes, display_name, texture)

    def prepare_for_processing(
        self,
        img_bytes: bytes,
        file_name: str,
        paintable: Gdk.Paintable,
    ):
        self.image_file_name = file_name
        self.image_bytes = img_bytes

        if self.navigation_view.get_visible_page_tag() != "process_page":
            self.navigation_view.push_by_tag("process_page")

        self.process_stack.set_visible_child_name("image_page")
        self.buttons_stack.set_visible_child_name("remove_button")

        self.picture_widget.set_paintable(paintable)

        self.is_busy = False

    def remove_bg(self):
        try:
            self.bg_free_image_bytes = self.image_processor.remove_bg(self.image_bytes)
            texture = Gdk.Texture.new_from_bytes(
                GLib.Bytes.new(self.bg_free_image_bytes)
            )

            GLib.idle_add(self.update_ui_after_processing, texture)
        except Exception:
            GLib.idle_add(self.handle_process_failure)

    def update_ui_after_processing(self, texture: Gdk.Texture):
        self.picture_widget.set_paintable(texture)
        self.set_processing_bg(False)
        self.buttons_stack.set_visible_child_name("save_button")

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
            callback=self.on_image_saved,
        )

    def on_image_saved(self, file: Gio.File, result: Gio.AsyncResult):
        success, _ = file.replace_contents_finish(result)

        if not success:
            self.toast_overlay.add_toast(Adw.Toast(title="Failed to save image"))
            return

        info = file.query_info(
            Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME, Gio.FileQueryInfoFlags.NONE
        )

        display_name = info.get_display_name() if info else file.get_basename()

        self.toast_overlay.add_toast(Adw.Toast(title=f"Saved to {display_name}"))

    def set_processing_bg(self, is_processing: bool):
        self.is_busy = is_processing
        self.remove_bg_spinner.set_visible(is_processing)
        self.remove_bg_button.set_sensitive(not is_processing)

    def show_loading_page(self):
        if self.navigation_view.get_visible_page_tag() != "process_page":
            self.navigation_view.push_by_tag("process_page")
        self.process_stack.set_visible_child_name("loading_page")

    def handle_load_failure(self, message="An error occurred"):
        self.is_busy = False
        self.toast_overlay.add_toast(Adw.Toast(title=message))
        if self.navigation_view.get_visible_page_tag() == "process_page":
            self.navigation_view.pop()

    def handle_process_failure(self):
        self.set_processing_bg(False)
        self.toast_overlay.add_toast(Adw.Toast(title="Could not remove background"))
