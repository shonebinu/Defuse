import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib

from .window import DefuseWindow

numba_cache_dir = (
    Path(GLib.get_user_cache_dir()) / "io.github.shonebinu.Defuse" / "numba-cache"
)
numba_cache_dir.mkdir(parents=True, exist_ok=True)

# rembg uses numba, which does a compilation for its first run.
# in flatpak environment, we need to set its cache path so that it does not try to compile every time
# https://numba.readthedocs.io/en/stable/developer/caching.html
os.environ["NUMBA_CACHE_DIR"] = str(numba_cache_dir)

# path where the models stored in flatpak build time
os.environ["U2NET_HOME"] = "/app/share/io.github.shonebinu.Defuse/rembg_models"

# disable auto re-downloading existing models
os.environ["MODEL_CHECKSUM_DISABLED"] = "1"


class DefuseApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id="io.github.shonebinu.Defuse",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            resource_base_path="/io/github/shonebinu/Defuse",
        )
        self.create_action("quit", lambda *_: self.quit(), ["<control>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = DefuseWindow(application=self)
        win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(
            application_name="defuse",
            application_icon="io.github.shonebinu.Defuse",
            developer_name="Shone Binu",
            version="0.1.0",
            developers=["Shone Binu"],
            copyright="© 2026 Shone Binu",
        )
        # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
        about.set_translator_credits(_("translator-credits"))
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        print("app.preferences action activated")

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = DefuseApplication()
    return app.run(sys.argv)
