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

    #dep_key can be either "schema/key" or "key", in the second case the settings schema of this widget is used
    def setup_dependency(self, dep_key):
        if dep_key is not None:
            self.dependency_invert = False
            if dep_key[0] == "!":
                self.dependency_invert = True
                dep_key = self.dep_key[1:]

            split = dep_key.split("/")
            if len(split) == 1:
                self.dep_settings = self.settings
            else:
                self.dep_settings = Gio.Settings(split[0])
            dep_key = split[-1]
            self.dep_settings.connect("changed::" + dep_key, self.on_gsettings_dependency_changed)
            self.on_gsettings_dependency_changed(self.dep_settings, dep_key)

    def apply_value(self, value):
        value = GLib.Variant(self.symbol, value)
        self.settings.set_value(self.key, value)

    def on_gsettings_changed(self, settings, key):
        self.update_value(settings.get_value(key).unpack())

    def on_gsettings_dependency_changed(self, settings, key):
        value = settings.get_value(key).unpack()
        if self.dependency_invert:
            value = not value
        self.set_sensitive(value)


class GSettingsCheckButton(CheckButton, BaseGSettingsWidget):
    symbol = "b"

    def __init__(self, description, schema, key, dep_key, **kwargs):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsCheckButton, self).__init__(description, value = self.value, **kwargs)
        self.setup_dependency(dep_key)

class GSettingsSpinButton(SpinButton, BaseGSettingsWidget):
    symbol = "i"

    def __init__(self, description, schema, key, dep_key, min, max, step, page, units):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsSpinButton, self).__init__(min, max, step, units, value = self.value, description = description, page = page)
        self.setup_dependency(dep_key)

class GSettingsEntry(Entry, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key, **kwargs):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsEntry, self).__init__(value = self.value, description = description, **kwargs)
        self.setup_dependency(dep_key)

class GSettingsFileChooser(FileChooser, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key, **kwargs):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsFileChooser, self).__init__(value = self.value, description = description, **kwargs)
        self.setup_dependency(dep_key)

class GSettingsFontButton(FontButton, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key, **kwargs):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsFontButton, self).__init__(value = self.value, description = description, **kwargs)
        self.setup_dependency(dep_key)

class GSettingsComboBox(ComboBox, BaseGSettingsWidget):
    def __init__(self, description, schema, key, dep_key, options, **kwargs):
        BaseGSettingsWidget.__init__(self, schema, key)
        super(GSettingsComboBox, self).__init__(options, value = self.value, description = description, **kwargs)
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

class GSettingsRange(Gtk.HBox):
    def __init__(self, label, low_label, hi_label, low_limit, hi_limit, inverted, valtype, exponential, schema, key, dep_key, **options):
        super(GSettingsRange, self).__init__()
        self.key = key
        self.dep_key = dep_key
        self.settings = Gio.Settings.new(schema)
        self.valtype = valtype

        if self.valtype == "int":
            self.value = self.settings.get_int(self.key) * 1.0
        elif self.valtype == "uint":
            self.value = self.settings.get_uint(self.key) * 1.0
        elif self.valtype == "double":
            self.value = self.settings.get_double(self.key) * 1.0
        self.label = Gtk.Label.new(label)
        self.label.set_alignment(1.0, 0.5)
        self.label.set_size_request(150, -1)
        self.low_label = Gtk.Label()
        self.low_label.set_alignment(0.5, 0.5)
        self.low_label.set_size_request(60, -1)
        self.hi_label = Gtk.Label()
        self.hi_label.set_alignment(0.5, 0.5)
        self.hi_label.set_size_request(60, -1)
        self.low_label.set_markup("<i><small>%s</small></i>" % low_label)
        self.hi_label.set_markup("<i><small>%s</small></i>" % hi_label)
        self.inverted = inverted
        self.exponential = exponential
        self._range = (hi_limit - low_limit) * 1.0
        self._step = options.get('adjustment_step', 1)
        self._min = low_limit * 1.0
        self._max = hi_limit * 1.0
        self.content_widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, (self._step / self._range))
        self.content_widget.set_size_request(300, 0)
        self.content_widget.set_value(self.to_corrected(self.value))
        self.content_widget.set_draw_value(False);

        self.grid = Gtk.Grid()
        if (label != ""):
            self.grid.attach(self.label, 0, 0, 1, 1)
        if (low_label != ""):
            self.grid.attach(self.low_label, 1, 0, 1, 1)
        self.grid.attach(self.content_widget, 2, 0, 1, 1)
        if (hi_label != ""):
            self.grid.attach(self.hi_label, 3, 0, 1, 1)
        self.pack_start(self.grid, True, True, 2)
        self._dragging = False
        self.content_widget.connect('value-changed', self.on_my_value_changed)
        self.content_widget.connect('button-press-event', self.on_mouse_down)
        self.content_widget.connect('button-release-event', self.on_mouse_up)
        self.content_widget.connect("scroll-event", self.on_mouse_scroll_event)
        self.content_widget.show_all()
        self.dependency_invert = False
        if self.dep_key is not None:
            if self.dep_key[0] == '!':
                self.dependency_invert = True
                self.dep_key = self.dep_key[1:]
            split = self.dep_key.split('/')
            self.dep_settings = Gio.Settings.new(split[0])
            self.dep_key = split[1]
            self.dep_settings.connect("changed::"+self.dep_key, self.on_dependency_setting_changed)
            self.on_dependency_setting_changed(self, None)

# halt writing gsettings during dragging
# it can take a long time to process all
# those updates, and the system can crash

    def on_mouse_down(self, widget, event):
        self._dragging = True

    def on_mouse_up(self, widget, event):
        self._dragging = False
        self.on_my_value_changed(widget)

    def on_mouse_scroll_event(self, widget, event):
        found, delta_x, delta_y = event.get_scroll_deltas()
        if found:
            add = delta_y < 0
            uncorrected = self.from_corrected(widget.get_value())
            if add:
                corrected = self.to_corrected(uncorrected + self._step)
            else:
                corrected = self.to_corrected(uncorrected - self._step)
            widget.set_value(corrected)
        return True

    def on_my_value_changed(self, widget):
        if self._dragging:
            return
        corrected = self.from_corrected(widget.get_value())
        if self.valtype == "int":
            self.settings.set_int(self.key, corrected)
        elif self.valtype == "uint":
            self.settings.set_uint(self.key, corrected)
        elif self.valtype == "double":
            self.settings.set_double(self.key, corrected)

    def on_dependency_setting_changed(self, settings, dep_key):
        if not self.dependency_invert:
            self.set_sensitive(self.dep_settings.get_boolean(self.dep_key))
        else:
            self.set_sensitive(not self.dep_settings.get_boolean(self.dep_key))

    def to_corrected(self, value):
        result = 0.0
        if self.exponential:
            k = (math.log(self._max) - math.log(self._min)) / (self._range / self._step)
            a = self._max / math.exp(k * self._range)
            cur_val_step = (1 / (k / math.log(value / a))) / self._range
            if self.inverted:
                result = 1 - cur_val_step
            else:
                result = cur_val_step
        else:
            if self.inverted:
                result = 1 - ((value - self._min) / self._range)
            else:
                result = (value - self._min) / self._range
        return result

    def from_corrected(self, value):
        result = 0.0
        if self.exponential:
            k = (math.log(self._max)-math.log(self._min))/(self._range / self._step)
            a = self._max / math.exp(k * self._range)
            if self.inverted:
                cur_val_step = (1 - value) * self._range
                result = a * math.exp(k * cur_val_step)
            else:
                cur_val_step = value * self._range
                result =  a * math.exp(k * cur_val_step)
        else:
            if self.inverted:
                result = ((1 - value) * self._range) + self._min
            else:
                result =  (value * self._range) + self._min
        return round(result)

    def add_mark(self, value, position, markup):
        self.content_widget.add_mark((value - self._min) / self._range, position, markup)

class GSettingsRangeSpin(Gtk.HBox):
    def __init__(self, label, schema, key, dep_key, **options):
        self.key = key
        self.dep_key = dep_key
        super(GSettingsRangeSpin, self).__init__()
        self.label = Gtk.Label.new(label)
        self.content_widget = Gtk.SpinButton()

        if (label != ""):
            self.pack_start(self.label, False, False, 2)
        self.pack_start(self.content_widget, False, False, 2)

        self.settings = Gio.Settings.new(schema)

        _min, _max = self.settings.get_range(self.key)[1]
        _increment = options.get('adjustment_step', 1)

        self.content_widget.set_range(_min, _max)
        self.content_widget.set_increments(_increment, _increment)
        #self.content_widget.set_editable(False)
        self.content_widget.set_digits(1)
        self.content_widget.set_value(self.settings.get_double(self.key))

        self.settings.connect("changed::"+self.key, self.on_my_setting_changed)
        self.content_widget.connect('value-changed', self.on_my_value_changed)
        self.dependency_invert = False
        if self.dep_key is not None:
            if self.dep_key[0] == '!':
                self.dependency_invert = True
                self.dep_key = self.dep_key[1:]
            split = self.dep_key.split('/')
            self.dep_settings = Gio.Settings.new(split[0])
            self.dep_key = split[1]
            self.dep_settings.connect("changed::"+self.dep_key, self.on_dependency_setting_changed)
            self.on_dependency_setting_changed(self, None)

    def on_my_setting_changed(self, settings, key):
        value = self.settings.get_double(self.key)
        if value != self.content_widget.get_value():
            self.content_widget.set_value(value)

    def on_my_value_changed(self, widget):
        self.settings.set_double(self.key, self.content_widget.get_value())

    def on_dependency_setting_changed(self, settings, dep_key):
        if not self.dependency_invert:
            self.set_sensitive(self.dep_settings.get_boolean(self.dep_key))
        else:
            self.set_sensitive(not self.dep_settings.get_boolean(self.dep_key))
