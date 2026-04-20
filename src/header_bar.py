from gi.repository import Adw, Gtk


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/header-bar.ui")
class DefuseHeaderBar(Adw.Bin):
    __gtype_name__ = "DefuseHeaderBar"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
