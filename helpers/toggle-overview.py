#!/usr/bin/python3
"""Toggle GNOME overview through its published session-bus property."""
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
result = bus.call_sync('org.gnome.Shell', '/org/gnome/Shell', 'org.freedesktop.DBus.Properties', 'Get',
                       GLib.Variant('(ss)', ('org.gnome.Shell', 'OverviewActive')),
                       None, Gio.DBusCallFlags.NONE, 3000, None)
bus.call_sync('org.gnome.Shell', '/org/gnome/Shell', 'org.freedesktop.DBus.Properties', 'Set',
              GLib.Variant('(ssv)', ('org.gnome.Shell', 'OverviewActive', GLib.Variant('b', not result.unpack()[0]))),
              None, Gio.DBusCallFlags.NONE, 3000, None)
