#!/usr/bin/env python

from GSettingsWidgets import *

UI_SCALES = {
    _("Auto"): 0,
    _("Normal"): 1,
    _("Double (Hi-DPI)"): 2
}

class Module:
    def __init__(self, content_box):
        keywords = _("logging, click")
        sidePage = SidePage(_("General"), "cs-general", keywords, content_box, module=self)
        self.sidePage = sidePage
        self.name = "general"
        self.comment = _("Miscellaneous Cinnamon preferences")
        self.category = "prefs"        

    def on_module_selected(self, switch_container):
        if not self.loaded:
            print "Loading General module"
            bg = SectionBg()        
            self.sidePage.add_widget(bg)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bg.add(vbox)

            section = Section(_("Desktop Scaling"))
            combo = GSettingsUIntComboBox(_("User interface scaling:"), "org.cinnamon.desktop.interface", "scaling-factor", None, UI_SCALES)
            section.add(combo)
            vbox.add(section)

            vbox.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))       

            section = Section(_("Miscellaneous Options"))
            button = GSettingsCheckButton(_("Disable compositing for full-screen windows"), "org.cinnamon.muffin", "unredirect-fullscreen-windows", None,
                tooltip = _("Select this option to let full-screen applications skip the compositing manager and run at maximum speed. Unselect it if you're experiencing screen-tearing in full screen mode."))
            section.add(button)
            section.add(GSettingsCheckButton(_("Enable timer when logging out or shutting down"), "org.cinnamon.SessionManager", "quit-delay-toggle", None))
            spin = GSettingsSpinButton(_("Timer delay:"), "org.cinnamon.SessionManager", "quit-time-delay", "org.cinnamon.SessionManager/quit-delay-toggle", 0, 36000, 1, 60, _("seconds"))
            section.add_indented(spin)
            section.add(GSettingsCheckButton(_("Log LookingGlass output to ~/.cinnamon/glass.log (Requires Cinnamon restart)"), "org.cinnamon", "enable-looking-glass-logs", None))
            vbox.add(section)
