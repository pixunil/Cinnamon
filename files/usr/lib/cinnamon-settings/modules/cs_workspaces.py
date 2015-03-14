#!/usr/bin/env python

from GSettingsWidgets import *

class Module:
    def __init__(self, content_box):
        keywords = _("workspace, osd, expo, monitor")
        sidePage = SidePage(_("Workspaces"), "cs-workspaces", keywords, content_box, module=self)
        self.sidePage = sidePage
        self.name = "workspaces"
        self.category = "prefs"
        self.comment = _("Manage workspace preferences")        

    def shouldLoad(self):
        return True

    def on_module_selected(self, switch_container):
        if not self.loaded:
            print "Loading Workspaces module"
            bg = SectionBg()        
            self.sidePage.add_widget(bg)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bg.add(vbox)

            section = Section(_("On-Screen Display (OSD)"))  
            section.add(GSettingsCheckButton(_("Enable workspace OSD"), "org.cinnamon", "workspace-osd-visible", None))
            section.add_indented(GSettingsSpinButton(_("Workspace OSD duration"), "org.cinnamon", "workspace-osd-duration", "workspace-osd-visible", 0, 2000, 50, 400, _("milliseconds")))
            section.add_indented(GSettingsSpinButton(_("Workspace OSD horizontal position"), "org.cinnamon", "workspace-osd-x", "workspace-osd-visible", 0, 100, 5, 50, _("percent of the monitor's width")))
            section.add_indented(GSettingsSpinButton(_("Workspace OSD vertical position"), "org.cinnamon", "workspace-osd-y", "workspace-osd-visible", 0, 100, 5, 50, _("percent of the monitor's height")))
            vbox.add(section)

            vbox.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))  
            
            section = Section(_("Miscellaneous Options"))  
            section.add(GSettingsCheckButton(_("Allow cycling through workspaces"), "org.cinnamon.muffin", "workspace-cycle", None))
            section.add(GSettingsCheckButton(_("Only use workspaces on primary monitor (requires Cinnamon restart)"), "org.cinnamon.muffin", "workspaces-only-on-primary", None))
            section.add(GSettingsCheckButton(_("Display Expo view as a grid"), "org.cinnamon", "workspace-expo-view-as-grid", None))
            vbox.add(section)
