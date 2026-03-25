import threading

import onnxruntime
from gi.repository import Adw, Gtk


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        print(onnxruntime.get_available_providers())

        self.rembg_session = None

        threading.Thread(target=self.load_rembg).start()

    def load_rembg(self):
        import rembg

        self.rembg_session = rembg.new_session(model_name="isnet-general-use")
        self.rembg_module = rembg

        print("done importing rembg")
