import io
import threading
from typing import Literal, Optional
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from pathlib import Path
from .header_bar import DefuseHeaderBar
from .processor import ImageProcessor
from PIL import Image


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

        self.is_busy = False
        self.image: Optional[Image.Image] = None
        self.image_file_name = "image"
        self.bg_free_image: Optional[Image.Image] = None

        self.supported_mimes = ImageProcessor.get_supported_mimes()
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

            self.process_selected_file(file)

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
        self.process_selected_file(file)

    def process_selected_file(self, file: Gio.File):
        self.show_loading_page()
        self.is_busy = True

        file_path = file.get_path()
        file_name = Path(file.get_basename() or "image").stem

        if not file_path:
            self.handle_load_failure()
            return

        threading.Thread(
            target=self.prepare_image_data,
            args=(file_path, file_name),
            daemon=True,
        ).start()

    def prepare_image_data(self, file_path: str, file_name: str):
        with Image.open(file_path) as img:
            img.load()

        texture = self.create_memory_texture(img)
        GLib.idle_add(self.prepare_for_processing, img, file_name, texture)

    def process_dropped_texture(self, texture: Gdk.Texture):
        if not (img_bytes := texture.save_to_tiff_bytes().get_data()):
            GLib.idle_add(self.handle_load_failure)
            return

        with io.BytesIO(img_bytes) as bytes:
            with Image.open(bytes) as img:
                img.load()

        GLib.idle_add(self.prepare_for_processing, img, "image", texture)

    def prepare_for_processing(
        self,
        image: Image.Image,
        file_name: str,
        paintable: Gdk.Paintable,
    ):
        self.image = image
        self.image_file_name = file_name

        if self.navigation_view.get_visible_page_tag() != "process_page":
            self.navigation_view.push_by_tag("process_page")

        self.process_stack.set_visible_child_name("image_page")
        self.buttons_stack.set_visible_child_name("remove_button")

        self.picture_widget.set_paintable(paintable)

        self.is_busy = False

    def remove_bg(self):
        try:
            if not self.image:
                return

            self.bg_free_image = ImageProcessor.remove_bg(self.image)
            texture = self.create_memory_texture(self.bg_free_image)

            GLib.idle_add(self.update_ui_after_processing, texture)
        except Exception:
            GLib.idle_add(self.handle_process_failure)

    def update_ui_after_processing(self, texture: Gdk.Texture):
        self.picture_widget.set_paintable(texture)
        self.set_processing_bg(False)
        self.buttons_stack.set_visible_child_name("save_button")

    def prompt_save_dialog(self):
        if not self.bg_free_image:
            return

        image_format = "PNG"
        file_dialog = Gtk.FileDialog(
            initial_name=f"{self.image_file_name}_nobg.{image_format.lower()}",
        )
        file_dialog.save(self, None, self.on_save_image, image_format)

    def on_save_image(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, format: str
    ):
        file = dialog.save_finish(result)
        threading.Thread(
            target=self.encode_and_save_image,
            args=(
                file,
                format,
            ),
            daemon=True,
        ).start()

    def encode_and_save_image(self, file: Gio.File, format: str):
        if not self.bg_free_image:
            return

        img_bytes = ImageProcessor.image_to_bytes(self.bg_free_image, format)
        GLib.idle_add(
            lambda: file.replace_contents_bytes_async(
                contents=GLib.Bytes.new(img_bytes),
                etag=None,
                make_backup=False,
                flags=Gio.FileCreateFlags.NONE,
                callback=self.on_image_saved,
            )
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

    def create_memory_texture(self, img: Image.Image) -> Gdk.MemoryTexture:
        # https://gitlab.gnome.org/World/Upscaler/-/blob/main/upscaler/media.py
        # use pillow for texture creation
        # since gtk image loaders only support limited formats
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        width, height = img.size
        return Gdk.MemoryTexture.new(
            width,
            height,
            Gdk.MemoryFormat.R8G8B8A8,
            GLib.Bytes.new(img.tobytes()),
            width * 4,
        )
