#!/usr/bin/env python

from SettingsWidgets import *
from gi.repository import Gio, Gtk, GObject, Gdk, GLib

class BaseGSettingsWidget(object):
    symbol = "s"

    def __init__(self, schema, key):
        self.key = key
        self.settings = Gio.Settings(schema)
        self.value = self.settings.get_value(self.key).unpack()
        self.settings.connect("changed::" + key, self.on_gsettings_changed)

    def setup_dependency(self, dep_key):
        if dep_key is not None:
            self.dependency_invert = False
            if dep_key[0] == "!":
                self.dependency_invert = True
                dep_key = self.dep_key[1:]

            split = dep_key.split("/")
            dep_settings = Gio.Settings(split[0])
            dep_key = split[1]
            dep_settings.connect("changed::" + dep_key, self.on_gsettings_dependency_changed)
            self.on_gsettings_dependency_changed(dep_settings, dep_key)

    def apply_value(self, value):
        value = GLib.Variant(self.symbol, value)
        self.settings.set_value(self.key, value)

    def on_gsettings_changed(self, settings, key):
        self.update_value(settings.get_value(key).unpack())

    def on_gsettings_dependency_changed(self, settings, key):
        value = settings.get_value(key).unpack()
        if not self.dependency_invert:
            self.update_dependency(value)
        else:
            self.update_dependency(not value)


class GSettingsCheckButton(CheckButton, BaseGSettingsWidget):
    symbol = "b"

    def __init__(self, description, schema, key, dep_key):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsCheckButton, self).__init__(self.value, description)
        self.setup_dependency(dep_key)

class GSettingsSpinButton(SpinButton, BaseGSettingsWidget):
    symbol = "i"

    def __init__(self, description, schema, key, dep_key, min, max, step, page, units):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsSpinButton, self).__init__(self.value, description, min, max, step, page, units)
        self.setup_dependency(dep_key)

class GSettingsEntry(Entry, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsEntry, self).__init__(self.value, description)
        self.setup_dependency(dep_key)

class GSettingsFileChooser(FileChooser, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsFileChooser, self).__init__(self.value, description)
        self.setup_dependency(dep_key)

class GSettingsFontButton(FontButton, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsFontButton, self).__init__(self.value, description)
        self.setup_dependency(dep_key)

class GSettingsComboBox(ComboBox, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key, options):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsComboBox, self).__init__(self.value, description, options)
        self.setup_dependency(dep_key)

class GSettingsIntComboBox(GSettingsComboBox, BaseGSettingsWidget):
    symbol = "i"

class GSettingsUIntComboBox(GSettingsComboBox, BaseGSettingsWidget):
    symbol = "u"

class GSettingsColorChooser(ColorChooser, BaseGSettingsWidget):
    def __init__(self, schema, key, dep_key):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsColorChooser, self).__init__(self.value)
        self.setup_dependency(dep_key)
