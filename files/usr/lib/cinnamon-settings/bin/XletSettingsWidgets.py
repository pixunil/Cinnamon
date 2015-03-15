#!/usr/bin/env python

try:
    import os
    import os.path
    import sys
    import string
    import gettext
    import collections
    import json
    import dbus
    import eyedropper
    import tweenEquations
    import math
    from gi.repository import Gio, Gtk, GObject, Gdk, GdkPixbuf
    from SettingsWidgets import *
except Exception, detail:
    print detail
    sys.exit(1)

home = os.path.expanduser("~")

class Factory():
    def __init__(self, file_name, instance_id, multi_instance, uuid):
        self.file = file_name
        self.settings = Settings(file_name, self, instance_id, multi_instance, uuid)
        self.widgets = collections.OrderedDict()
        self.file_obj = Gio.File.new_for_path(self.file)
        self.file_monitor = self.file_obj.monitor_file(Gio.FileMonitorFlags.SEND_MOVED, None)
        self.handler = self.file_monitor.connect("changed", self.on_file_changed)
        self.file_changed_timeout = None
        self.resume_timeout = None

    def create(self, key, setting_type, uuid):
        if setting_type in setting_dict:
            self.widgets[key] = setting_dict[setting_type](key, self.settings, uuid)
        else:
            print ("Invalid setting type '%s' supplied - please check your json file for %s" % (setting_type, uuid))

    def on_file_changed(self, file, other, event, data):
        if self.file_changed_timeout:
            GObject.source_remove(self.file_changed_timeout)
        self.file_changed_timeout = GObject.timeout_add(300, self.do_reload)

    def do_reload(self):
        self.settings.reload()
        for key in self.widgets.keys():
            self.widgets[key].on_settings_file_changed()
        self.file_changed_timeout = None
        return False

    def pause_monitor(self):
        self.file_monitor.cancel()
        self.handler = None

    def resume_monitor(self):
        if self.resume_timeout:
            GObject.source_remove(self.resume_timeout)
        self.resume_timeout = GObject.timeout_add(2000, self.do_resume)

    def do_resume(self):
        self.file_monitor = self.file_obj.monitor_file(Gio.FileMonitorFlags.SEND_MOVED, None)
        self.handler = self.file_monitor.connect("changed", self.on_file_changed)
        self.resume_timeout = None
        return False

    def reset_to_defaults(self):
        self.settings.reset_to_defaults()
        self.on_file_changed(None, None, None, None)

    def export_to_file(self, filename):
        try:
            self.settings.save(filename)
        except Exception, detail:
            warning = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                                        Gtk.ButtonsType.OK,
                                        _("Error saving file"))
            warning.format_secondary_text(_("There was a problem exporting the file to the selected location."))
            warning.run()
            warning.destroy()
            print detail

    def load_from_file(self, filename):
        try:
            self.settings.load_from_file(filename)
            self.on_file_changed(None, None, None, None)
        except Exception, detail:
            warning = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                                        Gtk.ButtonsType.OK,
                                        _("Error importing file"))
            warning.format_secondary_text(_("There was a problem importing the configuration file.\nPlease check that it is a valid JSON file, and is appropriate for this applet/desklet/extension.\nThe original configuration file is unchanged."))
            warning.run()
            warning.destroy()
            print detail

class Settings():
    def __init__(self, file_name, factory, instance_id, multi_instance, uuid):
        self.file_name = file_name
        self.factory = factory
        self.instance_id = instance_id
        self.multi_instance = multi_instance
        self.uuid = uuid
        try:
            self.tUser = gettext.translation(self.uuid, home+"/.local/share/locale").ugettext
        except IOError:
            try:
                self.tUser = gettext.translation(self.uuid, "/usr/share/locale").ugettext
            except IOError:
                self.tUser = None
        try:
            self.t = gettext.translation("cinnamon", "/usr/share/locale").ugettext
        except IOError:
            self.t = None
        self.reload()

    def reload (self):
        _file = open(self.file_name)
        raw_data = _file.read()
        self.data = {}
        self.data = json.loads(raw_data.decode('utf-8'), object_pairs_hook=collections.OrderedDict)
        _file.close()

    def save (self, name = None):
        if name is None:
            name = self.file_name
        self.factory.pause_monitor()
        if os.path.exists(name):
            os.remove(name)
        raw_data = json.dumps(self.data, indent=4)
        new_file = open(name, 'w+')
        new_file.write(raw_data)
        self.factory.resume_monitor()

    def get_data(self, key):
        return self.data[key]

    def get_key_exists(self, key):
        return key in self.data.keys()

    def real_update_dbus(self, key):
        self.factory.pause_monitor()
        session_bus = dbus.SessionBus()
        cinnamon_dbus = session_bus.get_object("org.Cinnamon", "/org/Cinnamon")
        setter = cinnamon_dbus.get_dbus_method('updateSetting', 'org.Cinnamon')
        payload = json.dumps(self.data[key])
        setter(self.uuid, self.instance_id, key, payload)
        self.factory.resume_monitor()

    def try_update_dbus(self, key):
        try:
            self.real_update_dbus(key)
        except Exception, e:
            print "Cinnamon not running, falling back to python settings engine: ", e
            self.save()

    def try_update_dbus_foreach(self):
        failed = False
        for key in self.data.keys():
            if "value" in self.data[key] and "default" in self.data[key]:
                try:
                    self.real_update_dbus(key)
                except Exception, e:
                    failed = True;
                    print "Cinnamon not running, falling back to python settings engine: ", e
        if failed:
            self.save()

    def set_value(self, key, val):
        self.data[key]["value"] = val
        self.try_update_dbus(key)

    def get_value(self, key):
        return self.data[key]["value"]

    def set_custom_value(self, key, val):
        self.data[key]["last-custom-value"] = val
        self.try_update_dbus(key)

    def reset_to_defaults(self):
        for key in self.data.keys():
            if "value" in self.data[key] and "default" in self.data[key]:
                self.data[key]["value"] = self.data[key]["default"]
        self.try_update_dbus_foreach()

    def load_from_file(self, filename):
        new_file = open(filename)
        new_raw = new_file.read()
        new_json = json.loads(new_raw.decode('utf-8'), object_pairs_hook=collections.OrderedDict)
        new_file.close()
        copy = self.data
        if copy["__md5__"] != new_json["__md5__"]:
            dialog = Gtk.Dialog(_("Possible incompatible versions"),
                                   None, 0,
                                  (Gtk.STOCK_NO, Gtk.ResponseType.NO,
                                   Gtk.STOCK_YES, Gtk.ResponseType.YES))
            text = Gtk.Label.new(_("The MD5 tags for the file you are trying to import and the existing file do not match.\n"
                             "This means the two files were generated by different versions of this applet, desklet or extension,\n"
                             "or possibly from a different one entirely.  Continuing with this procedure could yield unpredictable results.\n\n"
                             "Are you sure you want to proceed?"))
            box = dialog.get_content_area()
            box.add(text)
            box.show_all()
            response = dialog.run()

            if response == Gtk.ResponseType.NO:
                dialog.destroy()
                return
            dialog.destroy()
        self.data = new_json
        self.save()


class BaseXletWidget(object):
    def __init__(self, key, settings_obj, uuid):
        self.settings_obj = settings_obj
        if self.settings_obj.tUser:
            self.tUser = self.settings_obj.tUser
        else:
            self.tUser = None
        if self.settings_obj.t:
            self.t = self.settings_obj.t
        else:
            self.t = None
        self.key = key
        self.uuid = uuid
        self.handler = None

        self.data = self.settings_obj.get_data(self.key)
        for key in ("description", "tooltip", "units"):
            if key in self.data:
                self.data[key] = self.translate(self.data[key])
        if "options" in self.data:
            options = {}
            for option in self.data["options"]:
                toption = self.translate(option)
                options[toption] = self.data["options"][option]
            #replace the old, untranslated dir with the translated
            self.data["options"] = options

        self.dependents = []
        dep_key = self["dependency"]
        if dep_key is not None:
            if dep_key in self.settings_obj.factory.widgets:
                self.settings_obj.factory.widgets[dep_key].add_dependent(self.key)
            else:
                print ("Dependency key does not exist for key " + self.key + ".  The dependency MUST come before the dependent.  The UUID is: " + self.uuid)

    def __getitem__(self, key):
        return self.data.get(key, None)

    def __contains__(self, key):
        return key in self.data

    def translate(self, text):
        if text == "":
            return ""

        if self.tUser:
            result = self.tUser(text)
            if result != text:
                return text
        if self.t:
            return self.t(text)
        return text

    def on_settings_file_changed(self):
        pass

    def add_dependent(self, key):
        print ("Can only bind dependency to a CheckButton widget.  Ignoring dependency key.  The UUID is: " + self.uuid)

    def update_dependents(self):
        pass

    def get_instance_id(self):
        return self.settings_obj.instance_id

    def get_multi_instance(self):
        return self.settings_obj.multi_instance

class BaseXletSettingsWidget(BaseXletWidget):
    def apply_value(self, value):
        self.settings_obj.set_value(self.key, value)
        self.update_value(value)

    def on_settings_file_changed(self):
        self.update_value(self.settings_obj.get_value(self.key))

def set_tt(tt, *widgets):
    for widget in widgets:
        widget.set_tooltip_text(tt)


class IndentedHBox(Gtk.HBox):
    def __init__(self):
        super(IndentedHBox, self).__init__()
        indent = Gtk.Label.new('\t')
        self.pack_start(indent, False, False, 0)

    def add(self, item):
        self.pack_start(item, False, False, 0)

    def add_fill(self, item):
        self.pack_start(item, True, True, 0)

class XletSettingsHeader(Gtk.HBox, BaseXletWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsHeader, self).__init__()
        self.label = Gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_markup("<b>%s</b>" % self["description"])
        self.pack_start(self.label, False, False, 2)

class XletSettingsLabel(Gtk.HBox, BaseXletWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsLabel, self).__init__()
        self.label = Gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_markup(self.get_desc())
        self.pack_start(self.label, False, False, 2)

class XletSettingsSeparator(Gtk.HSeparator, BaseXletWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsSeparator, self).__init__()

class XletSettingsCheckButton(CheckButton, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsCheckButton, self).__init__(**self.data)

    def add_dependent(self, widget):
        self.dependents.append(widget)

class XletSettingsSpinButton(SpinButton, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsSpinButton, self).__init__(**self.data)

class XletSettingsEntry(Entry, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsEntry, self).__init__(**self.data)

class XletSettingsTextView(HBoxWidget, BaseXletSettingsWidget):
    expand = True

    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        self.content_widget = Gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
        self.content_widget.set_size_request(width=-1, height=self["height"] or 200)
        self.content_widget.set_policy(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                       vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        self.content_widget.set_shadow_type(type=Gtk.ShadowType.ETCHED_IN)
        self.textview = Gtk.TextView()
        self.textview.set_border_width(3)
        self.textview.set_wrap_mode(wrap_mode=Gtk.WrapMode.NONE)
        self.content_widget.add(self.textview)
        self.buffer = self.textview.get_buffer()

        super(XletSettingsTextView, self).__init__(**self.data)

        self.buffer.connect("changed", self.on_value_changed)

    def on_value_changed(self, widget):
        [start, end] = self.buffer.get_bounds()
        self.queue_value_changed(self.buffer.get_text(start, end, False))

    def update_value(self, value):
        self.buffer.set_text(value)

class XletSettingsColorChooser(HBoxWidget, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        self.content_widget = Gtk.ColorButton()

        super(XletSettingsColorChooser, self).__init__(**self.data)

        self.eyedropper = eyedropper.EyeDropper()
        self.pack_start(self.eyedropper, False, False, 2)

        self.content_widget.connect("color-set", self.on_value_changed)
        self.eyedropper.connect("color-picked", self.on_eyedropper_picked)

    def on_value_changed(self, widget):
        self.apply_value(self.get_rgba().to_string())

    def on_eyedropper_picked(self, widget, value):
        color = Gdk.RGBA()
        color.parse(value)
        self.content_widget.set_rgba(color)
        self.apply_value(value)

    def update_value(self, value):
        color = Gdk.RGBA()
        color.parse(value)
        self.content_widget.set_rgba(color)

class XletSettingsComboBox(ComboBox, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsComboBox, self).__init__(**self.data)

class XletSettingsRadioGroup(HBoxWidget, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        self.content_widget = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)

        self.entry = None
        self.custom_key = None
        self.custom_button = None
        group = None
        for key, value in self["options"].items():
            hbox = IndentedHBox()

            if value == "custom":
                self.custom_key = key
                button = Gtk.RadioButton.new_with_label_from_widget(group, "")
                group = button
                self.custom_button = button
                hbox.add(button)
                self.entry = Gtk.Entry()
                hbox.add(self.entry)
                button.orig_key = key
            else:
                button = Gtk.RadioButton.new_with_label_from_widget(group, key)
                group = button
                hbox.add(button)
                button.orig_key = key

            button.connect("toggled", self.on_value_changed)

            self.content_widget.pack_start(hbox, False, False, 2)
        self.group = group.get_group()

        super(XletSettingsRadioGroup, self).__init__(**self.data)

        if self.entry is not None:
            self.entry.set_text(self["last-custom-value"] or "")
            self.entry.connect("focus-in-event", self.on_custom_focus)
            self.entry.connect("changed", self.on_entry_changed)

    def on_custom_focus(self, event, widget):
        self.custom_button.set_active(True)

    def on_entry_changed(self, widget):
        self.queue_value_changed(self.entry.get_text())

    def on_button_activated(self, widget):
        if widget.get_active():
            if widget is self.custom_button:
                self.update_custom_settings_value()
            else:
                self.update_settings_value(widget.orig_key)

    def on_value_changed(self, model_key):
        self.apply_value(self["options"][model_key])
        if self.entry is not None:
            self.set_custom_val(self.entry.get_text())

    def update_value(self, value):
        _set = False
        for button in self.group:
            l = button.get_label()
            if l == "":
                l = self.custom_key
            if self["options"][l] == value:
                button.set_active(True)
                _set = True
                break
        if not _set:
            if self.entry is not None:
                self.custom_button.set_active(True)
                self.entry.set_text(value)
            else:
                self.custom_button.handler_block(self.custom_button.handler)
                self.custom_button.set_active(True)
                self.custom_button.handler_unblock(self.custom_button.handler)

    def update_dep_state(self, active):
        for button in self.group:
            button.set_sensitive(active)
        if self.entry is not None:
            self.entry.set_sensitive(active)


class XletSettingsFileChooser(FileChooser, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsFileChooser, self).__init__(**self.data)


class XletSettingsIconFileChooser(Entry, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        valid, self.width, self.height = Gtk.icon_size_lookup(Gtk.IconSize.BUTTON)
        self.image_button = Gtk.Button()
        self.preview = Gtk.Image.new()

        self.image_button.set_image(self.preview)

        super(XletSettingsIconFileChooser, self).__init__(**self.data)

        self.pack_start(self.image_button, False, False, 5)

        self.image_button.connect("clicked", self.on_button_pressed)

    def setup_image(self):
        if os.path.exists(self["value"]) and not os.path.isdir(self["value"]):
            img = GdkPixbuf.Pixbuf.new_from_file_at_size(self["value"], self.width, self.height)
            self.preview.set_from_pixbuf(img)
        else:
            self.preview.set_from_icon_name(self["value"], Gtk.IconSize.BUTTON)

    def on_button_pressed(self, widget):
        dialog = Gtk.FileChooserDialog(_("Choose an Icon"),
                                           None,
                                           Gtk.FileChooserAction.OPEN,
                                           (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        filter_text = Gtk.FileFilter()
        filter_text.set_name(_("Image files"))
        filter_text.add_mime_type("image/*")
        dialog.add_filter(filter_text)

        preview = Gtk.Image()
        dialog.set_preview_widget(preview)
        dialog.connect("update-preview", self.update_icon_preview_cb, preview)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            self.apply_value(filename)

        dialog.destroy()

    def update_value(self, value):
        self.content_widget.set_text(value)
        self.setup_image()

    #Updates the preview widget
    def update_icon_preview_cb(self, dialog, preview):
        filename = dialog.get_preview_filename()
        dialog.set_preview_widget_active(False)
        if os.path.isfile(filename):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
            if pixbuf is not None:
                if pixbuf.get_width() > 128:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 128, -1)
                elif pixbuf.get_height() > 128:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, -1, 128)
                preview.set_from_pixbuf(pixbuf)
                dialog.set_preview_widget_active(True)

class XletSettingsScale(HBoxWidget, BaseXletSettingsWidget):
    expand = True

    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        self.content_widget = Gtk.HScale.new_with_range(self["min"], self["max"], self["step"])

        super(XletSettingsScale, self).__init__(**self.data)

        self.content_widget.connect('value-changed', self.on_value_changed)
        self.content_widget.connect("scroll-event", self.on_mouse_scroll_event)

# TODO: Should we fix this in GTK? upscrolling should slide the slider to the right..right?
# This is already adjusted in Nemo as well.
    def on_mouse_scroll_event(self, widget, event):
        found, delta_x, delta_y = event.get_scroll_deltas()
        if found:
            add = delta_y < 0
            val = widget.get_value()
            if add:
                val += self["step"]
            else:
                val -= self["step"]
            widget.set_value(val)
        return True

    def on_value_changed(self, widget):
        self.queue_value_changed(self.content_widget.get_value())

    def update_value(self, value):
        self.content_widget.set_value(value)

class XletSettingsTweenChooser(TweenChooser, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsTweenChooser, self).__init__(**self.data)


SPECIAL_MODS = (["Super_L",    "<Super>"],
                ["Super_R",    "<Super>"],
                ["Alt_L",      "<Alt>"],
                ["Alt_R",      "<Alt>"],
                ["Control_L",  "<Primary>"],
                ["Control_R",  "<Primary>"],
                ["Shift_L",    "<Shift>"],
                ["Shift_R",    "<Shift>"])

# Ignore capslock and numlock when in teach mode
IGNORED_MOD_MASK = (int(Gdk.ModifierType.MOD2_MASK) | int(Gdk.ModifierType.LOCK_MASK))

class XletSettingsKeybinding(HBoxWidget, BaseXletSettingsWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletSettingsWidget.__init__(self, key, settings_obj, uuid)

        self.content_widget = Gtk.ButtonBox.new(Gtk.Orientation.HORIZONTAL)
        self.content_widget.set_layout(Gtk.ButtonBoxStyle.SPREAD)
        self.content_widget.set_hexpand(False)
        self.content_widget.set_halign(Gtk.Align.START)

        c = self.content_widget.get_style_context()
        c.add_class(Gtk.STYLE_CLASS_LINKED)

        self.buttons = []
        self.teach_button = None

        for _ in range(2):
            self.construct_button()

        self.event_id = None
        self.teaching = False

        super(XletSettingsKeybinding, self).__init__(**self.data)

    def construct_button(self):
        button = Gtk.Button(self["value"])
        button.set_tooltip_text(_("Click to set a new accelerator key.") +
                                _("  Press Escape or click again to cancel the operation." +
                                  "  Press Backspace to clear the existing keybinding."))
        button.connect("clicked", self.clicked)
        button.set_size_request(200, -1)
        button.set_hexpand(True)
        self.content_widget.add(button)

        self.buttons.append(button)

    def clicked(self, widget):
        self.teach_button = widget
        if not self.teaching:
            device = Gtk.get_current_event_device()
            if device.get_source() == Gdk.InputSource.KEYBOARD:
                self.keyboard = device
            else:
                self.keyboard = device.get_associated_device()

            self.keyboard.grab(self.get_window(), Gdk.GrabOwnership.WINDOW, False,
                               Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK,
                               None, Gdk.CURRENT_TIME)

            widget.set_label(_("Pick an accelerator"))
            self.event_id = self.connect( "key-release-event", self.on_key_release )
            self.teaching = True
        else:
            if self.event_id:
                self.disconnect(self.event_id)
            self.ungrab()
            self.set_button_text()
            self.teaching = False
            self.teach_button = None

    def on_key_release(self, widget, event):
        self.disconnect(self.event_id)
        self.ungrab()
        self.event_id = None
        if ((int(event.state) & 0xff & ~IGNORED_MOD_MASK) == 0) and event.keyval == Gdk.KEY_Escape:
            self.set_button_text()
            self.teaching = False
            self.teach_button = None
            return True
        if ((int(event.state) & 0xff & ~IGNORED_MOD_MASK) == 0) and event.keyval == Gdk.KEY_BackSpace:
            self.teaching = False
            self.value = self.place_value("")
            self.apply_value(self.value)
            self.teach_button = None
            return True
        accel_string = Gtk.accelerator_name(event.keyval, event.state)
        accel_string = self.sanitize(accel_string)
        self.value = self.place_value(accel_string)
        self.apply_value(self.value)
        self.teaching = False
        self.teach_button = None
        return True

    def place_value(self, string):
        i = self.buttons.index(self.teach_button)

        array = self.string_to_array(self.value)
        array[i] = string

        compacted_array = []
        for string in array:
            if string != "":
                compacted_array.append(string)
        return self.array_to_string(compacted_array)

    def array_to_string(self, array):
        string = ""
        done_once = False

        for binding in array:
            if done_once:
                string += "::"
            string += binding
            done_once = True

        return string

    def string_to_array(self, string):
        if not string or string == "":
            return ["",""]

        array = string.split("::", 1)
        while len(array) < 2:
            array.append("")

        return array

    def sanitize(self, string):
        accel_string = string.replace("<Mod2>", "")
        accel_string = accel_string.replace("<Mod4>", "")
        for single, mod in SPECIAL_MODS:
            if single in accel_string and mod in accel_string:
                accel_string = accel_string.replace(mod, "")
        return accel_string

    def update_value(self, value):
        self.set_button_text()

    def set_button_text(self):
        value_array = self.string_to_array(self["value"])
        i = 0
        while i < 2:
            if value_array[i] == "":
                self.buttons[i].set_label(_("<not set>"))
            else:
                self.buttons[i].set_label(value_array[i])
            i += 1

    def ungrab(self):
        self.keyboard.ungrab(Gdk.CURRENT_TIME)

class XletSettingsButton(Gtk.Button, BaseWidget, BaseXletWidget):
    def __init__(self, key, settings_obj, uuid):
        BaseXletWidget.__init__(self, key, settings_obj, uuid)
        super(XletSettingsButton, self).__init__(self["description"])
        BaseWidget.__init__(self, **self.data)
        self.connect('clicked', self.on_clicked)

    def on_clicked(self, widget):
        session_bus = dbus.SessionBus()
        cinnamon_dbus = session_bus.get_object("org.Cinnamon", "/org/Cinnamon")
        activate_cb = cinnamon_dbus.get_dbus_method('activateCallback', 'org.Cinnamon')
        activate_cb(self["callback"], self.get_instance_id(), self.get_multi_instance())

setting_dict = {
    "header"          :   XletSettingsHeader, # Not a setting, just a boldface header text
    "separator"       :   XletSettingsSeparator, # not a setting, a horizontal separator
    "label"           :   XletSettingsLabel, # Not a setting, just a text label
    "entry"           :   XletSettingsEntry,
    "textview"        :   XletSettingsTextView,
    "checkbox"        :   XletSettingsCheckButton,
    "spinbutton"      :   XletSettingsSpinButton,
    "filechooser"     :   XletSettingsFileChooser,
    "scale"           :   XletSettingsScale,
    "combobox"        :   XletSettingsComboBox,
    "colorchooser"    :   XletSettingsColorChooser,
    "radiogroup"      :   XletSettingsRadioGroup,
    "iconfilechooser" :   XletSettingsIconFileChooser,
    "tween"           :   XletSettingsTweenChooser,
    "keybinding"      :   XletSettingsKeybinding,
    "button"          :   XletSettingsButton # Not a setting, provides a button which triggers a callback in the applet/desklet
}
