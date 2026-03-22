# window.py
#
# Copyright 2026 Shone Binu
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from gi.repository import Adw, Gtk

# set path where the models are stored
os.environ["U2NET_HOME"] = "/app/share/io.github.shonebinu.Defuse/rembg_models"


@Gtk.Template(resource_path="/io/github/shonebinu/Defuse/window.ui")
class DefuseWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DefuseWindow"

    label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
