#!/usr/bin/env python

try:
    import os
    import os.path
    import commands
    import sys
    import string    
    import gettext
    from gi.repository import Gio, Gtk, GObject, Gdk
    from gi.repository import GdkPixbuf 
    from gi.repository import GConf
    import json
    import dbus
    import time
    from datetime import datetime
    import thread
    import urllib
    import lxml.etree
    import locale    
    import imtools
    from PIL import Image
    import tempfile
    import math
    import subprocess
    import tweenEquations

except Exception, detail:
    print detail
    sys.exit(1)

class EditableEntry (Gtk.Notebook):

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_FIRST, None,
                      (str,))
    }

    PAGE_BUTTON = 0
    PAGE_ENTRY = 1

    def __init__ (self):
        super(EditableEntry, self).__init__()

        self.label = Gtk.Label()
        self.entry = Gtk.Entry()
        self.button = Gtk.Button()

        self.button.set_alignment(0.0, 0.5)
        self.button.set_relief(Gtk.ReliefStyle.NONE)
        self.append_page(self.button, None);
        self.append_page(self.entry, None);  
        self.set_current_page(0)
        self.set_show_tabs(False)
        self.set_show_border(False)
        self.editable = False
        self.show_all()

        self.button.connect("released", self._on_button_clicked)
        self.button.connect("activate", self._on_button_clicked)
        self.entry.connect("activate", self._on_entry_validated)
        self.entry.connect("changed", self._on_entry_changed)

    def set_text(self, text):
        self.button.set_label(text)
        self.entry.set_text(text)

    def _on_button_clicked(self, button):
        self.set_editable(True)

    def _on_entry_validated(self, entry):
        self.set_editable(False)
        self.emit("changed", entry.get_text())

    def _on_entry_changed(self, entry):
        self.button.set_label(entry.get_text())

    def set_editable(self, editable):        
        if (editable):
            self.set_current_page(EditableEntry.PAGE_ENTRY)
        else:
            self.set_current_page(EditableEntry.PAGE_BUTTON)
        self.editable = editable

    def set_tooltip_text(self, tooltip):
        self.button.set_tooltip_text(tooltip)

    def get_editable(self):
        return self.editable

    def get_text(self):
        return self.entry.get_text()

class BaseChooserButton(Gtk.Button):
    def __init__ (self, has_button_label=False):
        super(BaseChooserButton, self).__init__()
        self.menu = Gtk.Menu()
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.button_image = Gtk.Image()
        self.button_box.add(self.button_image)
        if has_button_label:
            self.button_label = Gtk.Label()
            self.button_box.add(self.button_label)
        self.add(self.button_box)
        self.connect("button-release-event", self._on_button_clicked)

    def popup_menu_below_button (self, menu, widget):
        window = widget.get_window()
        screen = window.get_screen()
        monitor = screen.get_monitor_at_window(window)

        warea = screen.get_monitor_workarea(monitor)
        wrect = widget.get_allocation()
        mrect = menu.get_allocation()

        unused_var, window_x, window_y = window.get_origin()

        # Position left edge of the menu with the right edge of the button
        x = window_x + wrect.x + wrect.width
        # Center the menu vertically with respect to the monitor
        y = warea.y + (warea.height / 2) - (mrect.height / 2)

        # Now, check if we're still touching the button - we want the right edge
        # of the button always 100% touching the menu

        if y > (window_y + wrect.y):
            y = y - (y - (window_y + wrect.y))
        elif (y + mrect.height) < (window_y + wrect.y + wrect.height):
            y = y + ((window_y + wrect.y + wrect.height) - (y + mrect.height))

        push_in = True # push_in is True so all menu is always inside screen
        return (x, y, push_in)

    def _on_button_clicked(self, widget, event):
        if event.button == 1:
            self.menu.show_all()
            self.menu.popup(None, None, self.popup_menu_below_button, self, event.button, event.time)

class PictureChooserButton(BaseChooserButton):
    def __init__ (self, num_cols=4, button_picture_size=None, menu_pictures_size=None, has_button_label=False):
        super(PictureChooserButton, self).__init__(has_button_label)
        self.num_cols = num_cols
        self.button_picture_size = button_picture_size
        self.menu_pictures_size = menu_pictures_size
        self.row = 0
        self.col = 0
        self.progress = 0.0

        context = self.get_style_context()
        context.add_class("gtkstyle-fallback")

        self.connect_after("draw", self.on_draw) 

    def on_draw(self, widget, cr, data=None):
        if self.progress == 0:
            return False
        box = widget.get_allocation()

        context = widget.get_style_context()
        c = context.get_background_color(Gtk.StateFlags.SELECTED)

        max_length = box.width * .6
        start = (box.width - max_length) / 2
        y = box.height - 5

        cr.save()

        cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        cr.set_line_width(3)
        cr.set_line_cap(1)
        cr.move_to(start, y)
        cr.line_to(start + (self.progress * max_length), y)
        cr.stroke()

        cr.restore()
        return False

    def increment_loading_progress(self, inc):
        progress = self.progress + inc
        self.progress = min(1.0, progress)
        self.queue_draw()

    def reset_loading_progress(self):
        self.progress = 0.0
        self.queue_draw()

    def set_picture_from_file (self, path):
        if os.path.exists(path):
            if self.button_picture_size is None:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, -1, self.button_picture_size, True)
            self.button_image.set_from_pixbuf(pixbuf)

    def set_button_label(self, label):
        self.button_label.set_markup(label)

    def _on_picture_selected(self, menuitem, path, callback, id=None):
        if id is not None:
            result = callback(path, id)
        else:
            result = callback(path)
        
        if result:
            self.set_picture_from_file(path)            

    def clear_menu(self):
        menu = self.menu
        self.menu = Gtk.Menu()
        self.row = 0
        self.col = 0
        menu.destroy()

    def add_picture(self, path, callback, title=None, id=None):
        if os.path.exists(path):          
            if self.menu_pictures_size is None:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, -1, self.menu_pictures_size, True)
            image = Gtk.Image.new_from_pixbuf (pixbuf)  
            menuitem = Gtk.MenuItem()            
            if title is not None:
                vbox = Gtk.VBox()
                vbox.pack_start(image, False, False, 2)
                label = Gtk.Label()
                label.set_text(title)
                vbox.pack_start(label, False, False, 2)
                menuitem.add(vbox)
            else:
                menuitem.add(image)
            if id is not None:
                menuitem.connect('activate', self._on_picture_selected, path, callback, id)
            else:
                menuitem.connect('activate', self._on_picture_selected, path, callback)
            self.menu.attach(menuitem, self.col, self.col+1, self.row, self.row+1)
            self.col = (self.col+1) % self.num_cols
            if (self.col == 0):
                self.row = self.row + 1

    def add_separator(self):
        self.row = self.row + 1
        self.menu.attach(Gtk.SeparatorMenuItem(), 0, self.num_cols, self.row, self.row+1)

    def add_menuitem(self, menuitem):
        self.row = self.row + 1
        self.menu.attach(menuitem, 0, self.num_cols, self.row, self.row+1)

class SidePage:
    def __init__(self, name, icon, keywords, content_box = None, size = None, is_c_mod = False, is_standalone = False, exec_name = None, module=None):
        self.name = name
        self.icon = icon
        self.content_box = content_box
        self.widgets = []
        self.is_c_mod = is_c_mod
        self.is_standalone = is_standalone
        self.exec_name = exec_name
        self.module = module # Optionally set by the module so we can call on_module_selected() on it when we show it.
        self.keywords = keywords
        self.size = size
        self.topWindow = None
        self.builder = None
        if self.module != None:
            self.module.loaded = False

    def add_widget(self, widget):
        self.widgets.append(widget)        

    def build(self, switch_container):        
        # Clear all the widgets from the content box
        widgets = self.content_box.get_children()
        for widget in widgets:
            self.content_box.remove(widget)

        if (self.module is not None):
            self.module.on_module_selected(switch_container)
            self.module.loaded = True

        # Add our own widgets
        # C modules are sort of messy - they check the desktop type
        # (for Unity or GNOME) and show/hide UI items depending on
        # the result - so we cannot just show_all on the widget, it will
        # mess up these modifications - so for these, we just show the
        # top-level widget
        if not self.is_standalone:
            for widget in self.widgets:
                if hasattr(widget, 'expand'):
                    self.content_box.pack_start(widget, True, True, 2)
                else:
                    self.content_box.pack_start(widget, False, False, 2)
            if self.is_c_mod:
                self.content_box.show()
                children = self.content_box.get_children()
                for child in children:
                    child.show()
                    if child.get_name() == "c_box":
                        c_widgets = child.get_children()
                        if not c_widgets:
                            c_widget = self.content_box.c_manager.get_c_widget(self.exec_name)
                            if c_widget is not None:
                                child.pack_start(c_widget, False, False, 2)
                                c_widget.show()
                        else:
                            for c_widget in c_widgets:
                                c_widget.show()
            else:
                self.content_box.show_all()
                try:
                    self.check_third_arg()
                except:
                    pass
        else:
            subprocess.Popen(self.exec_name.split())

class CCModule:
    def __init__(self, label, mod_id, icon, category, keywords, content_box):
        sidePage = SidePage(label, icon, keywords, content_box, False, True, False, mod_id)
        self.sidePage = sidePage
        self.name = mod_id
        self.category = category

    def process (self, c_manager):
        if c_manager.lookup_c_module(self.name):
            c_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
            c_box.set_vexpand(False)
            c_box.set_name("c_box")
            self.sidePage.add_widget(c_box)
            return True
        else:
            return False

class SAModule:
    def __init__(self, label, mod_id, icon, category, keywords, content_box):
        sidePage = SidePage(label, icon, keywords, content_box, False, False, True, mod_id)
        self.sidePage = sidePage
        self.name = mod_id
        self.category = category

    def process (self):
        name = self.name.replace("gksudo ", "")
        name = name.replace("gksu ", "")
        return fileexists(name.split()[0])

def fileexists(program):

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, program)
        if is_exe(exe_file):
            return True
    return False

def walk_directories(dirs, filter_func, return_directories=False):
    # If return_directories is False: returns a list of valid subdir names
    # Else: returns a list of valid tuples (subdir-names, parent-directory)
    valid = []
    try:
        for thdir in dirs:
            if os.path.isdir(thdir):
                for t in os.listdir(thdir):
                    if filter_func(os.path.join(thdir, t)):
                        if return_directories:
                            valid.append([t, thdir])
                        else:
                            valid.append(t)
    except:
        pass
        #logging.critical("Error parsing directories", exc_info=True)
    return valid

def rec_mkdir(path):
    if os.path.exists(path):
        return
    
    rec_mkdir(os.path.split(path)[0])

    if os.path.exists(path):
        return
    os.mkdir(path)

class Section(Gtk.Box):
    def __init__(self, name):
        self.name = name
        super(Section, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_border_width(6)
        self.set_spacing(6)
        self.label = Gtk.Label()
        self.label.set_markup("<b>%s</b>" % self.name)
        hbox = Gtk.Box()
        hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        hbox.pack_start(self.label, False, False, 0)
        self.pack_start(hbox, False, True, 0)

    def add(self, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_margin_left(40)
        box.set_margin_right(40)
        box.pack_start(widget, False, True, 0)
        self.pack_start(box, False, False, 0)

    def add_expand(self, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_margin_left(40)
        box.set_margin_right(40)
        box.pack_start(widget, True, True, 0)
        self.pack_start(box, False, False, 0)

    def add_indented(self, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_margin_left(80)
        box.set_margin_right(10)
        box.pack_start(widget, False, True, 0)
        self.pack_start(box, False, False, 0)

    def add_indented_expand(self, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_margin_left(80)
        box.set_margin_right(10)
        box.pack_start(widget, True, True, 0)
        self.pack_start(box, False, False, 0)

class SectionBg(Gtk.Viewport):
    def __init__(self):
        Gtk.Viewport.__init__(self)
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        style = self.get_style_context()
        style.add_class("section-bg")
        self.expand = True # Tells CS to give expand us to the whole window

class SettingsStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)
        self.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.set_transition_duration(150)
        self.expand = True

class IndentedHBox(Gtk.HBox):
    def __init__(self):
        super(IndentedHBox, self).__init__()
        indent = Gtk.Label.new('\t')
        self.pack_start(indent, False, False, 0)

    def add(self, item):
        self.pack_start(item, False, True, 0)

    def add_expand(self, item):
        self.pack_start(item, True, True, 0)

class BaseWidget(object):
    _value_changed_timer = None

    def __init__(self, value = None, tooltip = "", **kwargs):
        if tooltip:
            self.set_tooltip_text(tooltip)

        if value is not None:
            self.update_value(value)

    #widgets call this method with the value in callbacks of events
    #this function just waits 100ms before applying the new value
    def queue_value_changed(self, value):
        if self._value_changed_timer:
            GObject.source_remove(self._value_changed_timer)
        self._value_changed_timer = GObject.timeout_add(100, self.on_timer_complete, value)

    def on_timer_complete(self, value):
        self._value_changed_timer = None
        self.apply_value(value)

class CheckButton(Gtk.CheckButton, BaseWidget):
    def __init__(self, description = "", **kwargs):
        super(CheckButton, self).__init__(label = description)
        BaseWidget.__init__(self, **kwargs)

        self.connect("toggled", self.on_value_changed)

    def on_value_changed(self, widget):
        self.apply_value(self.get_active())

    def update_value(self, value):
       self.set_active(value)

class HBoxWidget(Gtk.HBox, BaseWidget):
    #set expand to true to have the content widget take all the width
    expand = False

    #before initing a HBoxWidget, self.content_widget must be defined
    def __init__(self, description = "", indent = 0, **kwargs):
        super(HBoxWidget, self).__init__()
        BaseWidget.__init__(self, **kwargs)

        if indent:
            label = Gtk.Label("\t" * indent)
            self.pack_start(label, False, False, 2)

        if description:
            label = Gtk.Label(description)
            self.pack_start(label, False, False, 2)

        if self.expand:
            self.pack_start(self.content_widget, True, True, 2)
        else:
            self.pack_start(self.content_widget, False, False, 2)

class SpinButton(HBoxWidget):
    def __init__(self, min, max, step, units, page = None, **kwargs):
        self.content_widget = Gtk.SpinButton()
        self.content_widget.set_range(min, max)
        if page is None:
            page = step
        self.content_widget.set_increments(step, page)

        super(SpinButton, self).__init__(**kwargs)

        if units:
            label = Gtk.Label(units)
            self.pack_start(label, False, False, 2)

        #is this piece of code needed?
        #if range[0] == "range":
        #    rangeDefault = (1 << 32) - 1
        #    rangeMin = rangeDefault
        #    rangeMax = rangeDefault
        #    range = range[1]
        #    rangeMin = range[0] if range[0] < rangeDefault else rangeDefault
        #    rangeMax = range[1] if range[1] < rangeDefault else rangeDefault
        #    self.min = min if min > rangeMin else rangeMin
        #    self.max = max if max < rangeMax else rangeMax

        self.content_widget.connect("value-changed", self.on_value_changed)
        self._value_changed_timer = None

    def on_value_changed(self, widget):
        if self._value_changed_timer:
            GObject.source_remove(self._value_changed_timer)
        self._value_changed_timer = GObject.timeout_add(300, self.update_settings_value)

    def update_settings_value(self):
        self.apply_value(self.content_widget.get_value())
        self._value_changed_timer = None
        return False

    def update_value(self, value):
        self.content_widget.set_value(value)

class Entry(HBoxWidget):
    def __init__(self, **kwargs):
        self.content_widget = Gtk.Entry()
        super(Entry, self).__init__(**kwargs)

        self.content_widget.connect("changed", self.on_value_changed)

    def on_value_changed(self, widget):
        self.queue_value_changed(self.content_widget.get_text())

    def update_value(self, value):
        self.content_widget.set_text(value)


class FileChooser(HBoxWidget):
    def __init__(self, show_none_cb = False, **kwargs):
        self.content_widget = Gtk.FileChooserButton()
        super(FileChooser, self).__init__(**kwargs)

        self.show_none_cb = show_none_cb

        if self.show_none_cb:
            self.show_none_cb_widget = Gtk.CheckButton(_("None"))
            self.show_none_cb_widget.set_active(value == "")
            self.pack_start(self.show_none_cb_widget, False, False, 5)
            if value == "":
                self.content_widget.set_sensitive(False)

        self.content_widget.connect('file-set', self.on_value_changed)
        if self.show_none_cb:
            self.show_none_cb_widget.connect('toggled', self.on_value_changed)

    def on_value_changed(self, widget):
        if self.show_none_cb:
            if self.show_none_cb_widget.get_active():
                value = ""
                self.content_widget.set_sensitive(False)
            else:
                value = self.content_widget.get_filename()
                if value == None:
                    value = ""
                self.content_widget.set_sensitive(True)
        else:
            value = self.content_widget.get_filename()
            if value == None:
                value = ""
        self.apply_value(value)

    def update_value(self, value):
        self.content_widget.set_filename(value)

class FontButton(HBoxWidget):
    def __init__(self, **kwargs):
        self.content_widget = Gtk.FontButton()
        super(FontButton, self).__init__(**kwargs)

        self.content_widget.connect('font-set', self.on_value_changed)

    def on_value_changed(self, widget):
        self.apply_value(widget.get_font_name())

    def update_value(self, value):
        self.content_widget.set_font_name(value)

class ComboBox(HBoxWidget):
    def __init__(self, options, **kwargs):
        self.iters = {}
        for option in options:
            if isinstance(options[option], basestring):
                self.model = Gtk.ListStore(str, str)
            elif isinstance(options[option], int):
                self.model = Gtk.ListStore(str, int)
            elif isinstance(options[option], bool):
                self.model = Gtk.ListStore(str, bool)
            else:
                self.model = Gtk.ListStore(str, float)
            break
        self.content_widget = Gtk.ComboBox.new_with_model(self.model)

        for option in options:
            iter = self.model.insert_before(None, None)
            self.model.set_value(iter, 0, option)
            self.model.set_value(iter, 1, options[option])
            self.iters[options[option]] = iter

        super(ComboBox, self).__init__(**kwargs)

        renderer_text = Gtk.CellRendererText()
        self.content_widget.pack_start(renderer_text, True)
        self.content_widget.add_attribute(renderer_text, "text", 0)

        self.content_widget.connect("changed", self.on_value_changed)

    def on_value_changed(self, widget):
        tree_iter = widget.get_active_iter()
        if tree_iter != None:
            self.apply_value(self.model[tree_iter][1])

    def update_value(self, value):
        if value in self.iters:
            self.content_widget.set_active_iter(self.iters[value])
        else:
            self.content_widget.set_active(-1)


class ColorChooser(Gtk.ColorButton, BaseWidget):
    def __init__(self, value, **kwargs):
        super(ColorChooser, self).__init__()
        BaseWidget.__init__(self, **kwargs)

        self.connect("color-set", self.on_value_changed)

    def on_value_changed(self, widget):
        self.apply_value(self.get_color().to_string())

    def update_value(self, value):
        self.set_color(Gdk.color_parse(value))

class TweenChooser(HBoxWidget):
    def __init__(self, **kwargs):
        self.content_widget = BaseChooserButton()

        self.build_menuitem("None", 0, 0)

        row = 1
        for main in ["Quad", "Cubic", "Quart", "Quint", "Sine", "Expo", "Circ", "Elastic", "Back", "Bounce"]:
            col = 0
            for prefix in ["In", "Out", "InOut", "OutIn"]:
                self.build_menuitem(prefix + main, col, row)
                col += 1
            row += 1

        self.content_widget.set_size_request(128, -1)

        super(TweenChooser, self).__init__(**kwargs)

    def build_menuitem(self, name, col, row):
        menuitem = TweenMenuItem("ease" + name)
        menuitem.connect("activate", self.change_value)
        self.content_widget.menu.attach(menuitem, col, col + 1, row, row + 1)

    def bind_time(self, key):
        self.settings.connect("changed::" + key, self.update_time)
        self.update_time(self.settings, key)

    def update_time(self, settings, key):
        time = settings.get_int(key) / 10
        for item in self.content_widget.menu.get_children():
            item.duration = time

    def change_value(self, widget):
        self.apply_value(widget.name)

    def update_value(self, value):
        self.content_widget.set_label(value)

class TweenMenuItem(Gtk.MenuItem):
    width = 96
    height = 48

    state = -1
    duration = 50

    timer = None

    def __init__(self, name):
        super(TweenMenuItem, self).__init__()

        self.name = name
        self.function = getattr(tweenEquations, name)

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        box = Gtk.Box()
        self.vbox.add(box)

        self.graph = Gtk.DrawingArea()
        box.add(self.graph)
        self.graph.set_size_request(self.width, self.height)
        self.graph.connect("draw", self.draw_graph)

        self.arr = Gtk.DrawingArea()
        box.pack_end(self.arr, False, False, 0)
        self.arr.set_size_request(5, self.height)
        self.arr.connect("draw", self.draw_arr)

        self.connect("enter-notify-event", self.start_animation)
        self.connect("leave-notify-event", self.end_animation)

        label = Gtk.Label()
        self.vbox.add(label)
        label.set_text(name)

    def draw_graph(self, widget, ctx):
        width = self.width - 2.
        height = self.height / 8.

        context = widget.get_style_context()
        if self.state == -1:
            c = context.get_background_color(Gtk.StateFlags.SELECTED)
        else:
            c = context.get_color(Gtk.StateFlags.NORMAL)
        ctx.set_source_rgb(c.red, c.green, c.blue)

        ctx.move_to(1, height * 6)
        for i in range(int(width)):
            ctx.line_to(i + 2, self.function(i + 1., height * 6, -height * 4, width))
        ctx.stroke()

    def draw_arr(self, widget, ctx):
        if self.state < 0:
            return
        height = self.height / 8.

        context = widget.get_style_context()
        c = context.get_color(Gtk.StateFlags.NORMAL)
        ctx.set_source_rgb(c.red, c.green, c.blue)

        ctx.arc(5, self.function(self.state, height * 6, -height * 4, self.duration - 1), 5, math.pi / 2, math.pi * 1.5)
        ctx.fill()

    def start_animation(self, a, b):
        self.state = 0.
        self.graph.queue_draw()
        self.arr.queue_draw()

        self.timer = GObject.timeout_add(400, self.frame)

    def end_animation(self, a, b):
        if self.timer:
            GObject.source_remove(self.timer)
            self.timer = None

        self.state = -1
        self.graph.queue_draw()
        self.arr.queue_draw()

    def frame(self):
        self.timer = None
        self.state += 1

        if self.state >= self.duration:
            return

        self.arr.queue_draw()
        self.timer = GObject.timeout_add(10, self.frame)
