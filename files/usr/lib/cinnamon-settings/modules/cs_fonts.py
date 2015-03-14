#!/usr/bin/env python

from GSettingsWidgets import *
from gi.repository import Gtk

AA_OPTIONS = {
    _("None"): "none",
    _("Grayscale"): "grayscale",
    _("Rgba"): "rgba"
}

HINTING_OPTIONS = {
    _("None"): "none",
    _("Slight"): "slight",
    _("Medium"): "medium",
    _("Full"): "full"
}

class Module:
    def __init__(self, content_box):
        keywords = _("font, size, small, large")
        sidePage = SidePage(_("Fonts"), "cs-fonts", keywords, content_box, module=self)
        self.sidePage = sidePage
        self.name = "fonts"
        self.category = "appear"
        self.comment = _("Configure system fonts")        

    def on_module_selected(self, switch_container):
        if not self.loaded:
            print "Loading Fonts module"
            bg = SectionBg()        
            self.sidePage.add_widget(bg)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bg.add(vbox)
            
            section = Section(_("Font Selection"))
            section.add(self.make_combo_group(GSettingsFontButton, _("Default font"), "org.cinnamon.desktop.interface", "font-name", None))
            section.add(self.make_combo_group(GSettingsFontButton, _("Desktop font"), "org.nemo.desktop", "font", None))
            section.add(self.make_combo_group(GSettingsFontButton, _("Document font"), "org.gnome.desktop.interface", "document-font-name", None))
            section.add(self.make_combo_group(GSettingsFontButton, _("Monospace font"), "org.gnome.desktop.interface", "monospace-font-name", None))
            section.add(self.make_combo_group(GSettingsFontButton, _("Window title font"), "org.cinnamon.desktop.wm.preferences", "titlebar-font", None))
            vbox.add(section)
            
            vbox.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

            section = Section(_("Font Settings"))
            section.add(self.make_combo_group(GSettingsRangeSpin, _("Text scaling factor"), "org.cinnamon.desktop.interface", "text-scaling-factor", None))
            section.add(self.make_combo_group(GSettingsComboBox, _("Antialiasing"), "org.cinnamon.settings-daemon.plugins.xsettings", "antialiasing", AA_OPTIONS))
            section.add(self.make_combo_group(GSettingsComboBox, _("Hinting"), "org.cinnamon.settings-daemon.plugins.xsettings", "hinting", HINTING_OPTIONS))
            vbox.add(section)

    def make_combo_group(self, widget, group_label, root, key, stuff):
        self.size_groups = getattr(self, "size_groups", [Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL) for x in range(2)])
        
        box = IndentedHBox()
        label = Gtk.Label()
        label.set_markup(group_label)
        label.props.xalign = 0.0
        self.size_groups[0].add_widget(label)
        box.pack_start(label, False, False, 0)

        if (key == "text-scaling-factor"):
            w = widget("", root, key, None, adjustment_step = 0.1)
        elif (key == "antialiasing"):
            w = widget("", root, key, None, stuff,
                tooltip = _("Antialiasing makes on screen text smoother and easier to read"))
        elif (key == "hinting"):
            w = widget("", root, key, None, stuff,
                tooltip = _("Hinting allows for producing clear, legible text on screen."))
        else:
            w = widget("", root, key, None)

        self.size_groups[1].add_widget(w)
        box.pack_start(w, False, False, 15)
        
        return box
