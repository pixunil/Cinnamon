#!/usr/bin/env python

from SettingsWidgets import *
from gi.repository.Gtk import SizeGroup, SizeGroupMode

EFFECTS_SETS = {
    "none":    ["none",    "none",    "none",    "none",  "none",  "none"],
    "scale":   ["scale",   "scale",   "scale",   "scale", "scale", "scale"],
    "fade":    ["fade",    "fade",    "fade",    "scale", "scale", "scale"],
    "blend":   ["blend",   "blend",   "blend",   "scale", "scale", "scale"],
    "move":    ["move",    "move",    "move",    "scale", "scale", "scale"],
    "flyUp":   ["flyUp",   "flyUp",   "flyUp",   "scale", "scale", "scale"],
    "flyDown": ["flyDown", "flyDown", "flyDown", "scale", "scale", "scale"]
}

TRANISTIONS_SETS = {
    "normal": ["easeOutSine",    "easeInBack",    "easeInSine",  "easeInBack", "easeOutBounce",  "easeInBack"],
    "extra":  ["easeOutElastic", "easeOutBounce", "easeOutExpo", "easeInExpo", "easeOutElastic", "easeInExpo"]
}

COMBINATIONS = [
    #display label  effect set  transition set
    [_("None"),        "none",    "normal"],
    [_("Scale"),       "scale",   "normal"],
    [_("Fancy Scale"), "scale",   "extra"],
    [_("Fade"),        "fade",    "normal"],
    [_("Blend"),       "blend",   "normal"],
    [_("Move"),        "move",    "normal"],
    [_("Fly up"),      "flyUp",   "normal"],
    [_("Fly down"),    "flyDown", "normal"]
]

class Module:
    def __init__(self, content_box):
        keywords = _("effects, fancy, window")
        sidePage = SidePage(_("Effects"), "cs-desktop-effects", keywords, content_box, module=self)
        self.sidePage = sidePage
        self.name = "effects"
        self.category = "appear"
        self.comment = _("Control Cinnamon visual effects.")            

    def on_module_selected(self):
        if not self.loaded:
            print "Loading Effects module"
            bg = SectionBg()        
            self.sidePage.add_widget(bg)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bg.add(vbox)

            effect_sets = []
            for i in COMBINATIONS:
                value = [
                    EFFECTS_SETS[i[1]],
                    TRANISTIONS_SETS[i[2]]
                ]
                effect_sets.append([value, i[0], i[1]])

            effect_sets.append([None, _("Custom"), "none"])

            section = Section(_("Enable Effects"))
            section.add(GSettingsCheckButton(_("Enable desktop effects"), "org.cinnamon", "desktop-effects", None))
            section.add_indented(GSettingsCheckButton(_("Enable session startup animation"), "org.cinnamon", "startup-animation", "org.cinnamon/desktop-effects"))
            section.add_indented(GSettingsCheckButton(_("Enable desktop effects on dialog boxes"), "org.cinnamon", "desktop-effects-on-dialogs", "org.cinnamon/desktop-effects"))

            self.chooser = EffectSetChooserButton("org.cinnamon", "desktop-effects-%s-%s", "org.cinnamon/desktop-effects", effect_sets)
            self.chooser.on_value_changed = self.update_section

            box = Gtk.HBox()
            box.pack_start(Gtk.Label.new(_("Effect style")), False, False, 2)
            box.pack_start(self.chooser, False, False, 2)
            section.add_indented(box)

            section.add(GSettingsCheckButton(_("Enable fade effect on Cinnamon scrollboxes (like the Menu application list)"), "org.cinnamon", "enable-vfade", None))
            vbox.add(section)

            #it seems that Gtk doesn't automatically hide the separator if we hide the section after it
            self.separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
            vbox.add(self.separator)

            self.custom_effects = Section(_("Customize Effects"))
            #self.custom_effects.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

            #MAPPING WINDOWS
            effects = [
                ["none",    _("None")],
                ["scale",   _("Scale")],
                ["fade",    _("Fade")],
                ["blend",   _("Blend")],
                ["move",    _("Move")],
                ["flyUp",   _("Fly up")],
                ["flyDown", _("Fly down")]
            ]
            self.make_effect_group(_("Mapping windows:"), "map", effects)

            #CLOSING WINDOWS
            self.make_effect_group(_("Closing windows:"), "close", effects)

            #MINIMIZING WINDOWS
            effects[:1] += [["traditional", _("Traditional")]]
            self.make_effect_group(_("Minimizing windows:"), "minimize", effects)

            #MAXIMIZING WINDOWS
            effects = [["none", _("None")], ["scale", _("Scale")]]
            self.make_effect_group(_("Maximizing windows:"), "maximize", effects)

            #UNMAXIMIZING WINDOWS
            self.make_effect_group(_("Unmaximizing windows:"), "unmaximize", effects)

            #TILING WINDOWS
            self.make_effect_group(_("Tiling and snapping windows:"), "tile", effects)

            vbox.add(self.custom_effects)

            self.custom_effects.connect("show", self.update_section)

    def update_section(self, *args):
        EffectSetChooserButton.on_value_changed(self.chooser)

        self.separator.set_visible(not self.chooser.value)
        self.custom_effects.set_visible(not self.chooser.value)

    def make_effect_group(self, group_label, key, effects):
        tmin, tmax, tstep, tdefault = (0, 2000, 50, 200)
        self.size_groups = getattr(self, "size_groups", [SizeGroup.new(SizeGroupMode.HORIZONTAL) for x in range(4)])
        root = "org.cinnamon"
        path = "org.cinnamon/desktop-effects"
        template = "desktop-effects-%s-%s"
        box = Gtk.HBox()
        label = Gtk.Label()
        label.set_markup(group_label)
        label.props.xalign = 0.0
        self.size_groups[0].add_widget(label)
        box.add(label)
        w = EffectChooserButton(root, template % (key, "effect"), path, effects, key)
        self.size_groups[1].add_widget(w)
        box.add(w)
        t = TweenChooserButton(root, template % (key, "transition"), path)
        self.size_groups[2].add_widget(t)
        box.add(t)
        w.bind_transition(template % (key, "transition"))
        w = GSettingsSpinButton("", root, template % (key, "time"), path, tmin, tmax, tstep, tdefault, _("milliseconds"))
        self.size_groups[3].add_widget(w)
        box.add(w)

        self.custom_effects.add(box)
