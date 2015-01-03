// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

const Clutter = imports.gi.Clutter;
const Lang = imports.lang;
const Meta = imports.gi.Meta;
const St = imports.gi.St;
const Cinnamon = imports.gi.Cinnamon;
const Mainloop = imports.mainloop;
const Gio = imports.gi.Gio;
const AppletManager = imports.ui.appletManager;
const AppSwitcher = imports.ui.appSwitcher.appSwitcher;
const CoverflowSwitcher = imports.ui.appSwitcher.coverflowSwitcher;
const TimelineSwitcher = imports.ui.appSwitcher.timelineSwitcher;
const ClassicSwitcher = imports.ui.appSwitcher.classicSwitcher;
const WindowEffects = imports.ui.windowEffects;

const Main = imports.ui.main;
const Tweener = imports.ui.tweener;

const WINDOW_ANIMATION_TIME = 0.25;
const DIM_TIME = 0.500;
const DIM_DESATURATION = 0.6;
const DIM_BRIGHTNESS = -0.1;
const UNDIM_TIME = 0.250;

function getTopInvisibleBorder(metaWindow) {
    let outerRect = metaWindow.get_outer_rect();
    let inputRect = metaWindow.get_input_rect();
    return outerRect.y - inputRect.y;
}

function WindowDimmer(actor) {
    this._init(actor);
}

WindowDimmer.prototype = {
    _init: function(actor) {

        this._desaturateEffect = new Clutter.DesaturateEffect();
        this._brightnessEffect = new Clutter.BrightnessContrastEffect();
        actor.add_effect(this._desaturateEffect);
        actor.add_effect(this._brightnessEffect);

        this.actor = actor;
        this._dimFactor = 0.0;
    },

    setEnabled: function(enabled) {
        this._desaturateEffect.enabled = enabled;
        this._brightnessEffect.enabled = enabled;
    },

    set dimFactor(factor) {
        this._dimFactor = factor;
        this._desaturateEffect.set_factor(factor * DIM_DESATURATION);
        this._brightnessEffect.set_brightness(factor * DIM_BRIGHTNESS);
    },

    get dimFactor() {
       return this._dimFactor;
    }
};

function getWindowDimmer(actor) {
    if (!actor._windowDimmer)
        actor._windowDimmer = new WindowDimmer(actor);

    return actor._windowDimmer;
}

function WindowManager() {
    this._init();
}

WindowManager.prototype = {
    _init : function() {
        this._cinnamonwm =  global.window_manager;

        this._minimizing = [];
        this._maximizing = [];
        this._unmaximizing = [];
        this._tiling = [];
        this._mapping = [];
        this._destroying = [];

        this.effects = {
            map: new WindowEffects.Map(this),
            close: new WindowEffects.Close(this),
            minimize: new WindowEffects.Minimize(this),
            unminimize: new WindowEffects.Unminimize(this),
            tile: new WindowEffects.Tile(this),
            maximize: new WindowEffects.Maximize(this),
            unmaximize: new WindowEffects.Unmaximize(this)
        };

        this._snap_osd = null;
        this._workspace_osd = null;

        this._dimmedWindows = [];

        this._animationBlockCount = 0;

        this._switchData = null;
        this._cinnamonwm.connect('kill-switch-workspace', Lang.bind(this, this._switchWorkspaceDone));
        this._cinnamonwm.connect('kill-window-effects', Lang.bind(this, this._killWindowEffects));

        this._cinnamonwm.connect('switch-workspace', Lang.bind(this, this._switchWorkspace));
        this._cinnamonwm.connect('minimize', Lang.bind(this, this._minimizeWindow));
        this._cinnamonwm.connect('maximize', Lang.bind(this, this._maximizeWindow));
        this._cinnamonwm.connect('unmaximize', Lang.bind(this, this._unmaximizeWindow));
        this._cinnamonwm.connect('tile', Lang.bind(this, this._tileWindow));
        this._cinnamonwm.connect('map', Lang.bind(this, this._mapWindow));
        this._cinnamonwm.connect('destroy', Lang.bind(this, this._destroyWindow));

        Meta.keybindings_set_custom_handler('move-to-workspace-left',
                                            Lang.bind(this, this._moveWindowToWorkspaceLeft));
        Meta.keybindings_set_custom_handler('move-to-workspace-right',
                                            Lang.bind(this, this._moveWindowToWorkspaceRight));

        Meta.keybindings_set_custom_handler('switch-to-workspace-left',
                                            Lang.bind(this, this._showWorkspaceSwitcher));
        Meta.keybindings_set_custom_handler('switch-to-workspace-right',
                                            Lang.bind(this, this._showWorkspaceSwitcher));
        Meta.keybindings_set_custom_handler('switch-to-workspace-up',
                                            Lang.bind(this, this._showWorkspaceSwitcher));
        Meta.keybindings_set_custom_handler('switch-to-workspace-down',
                                            Lang.bind(this, this._showWorkspaceSwitcher));
        Meta.keybindings_set_custom_handler('switch-windows',
                                            Lang.bind(this, this._startAppSwitcher));
        Meta.keybindings_set_custom_handler('switch-group',
                                            Lang.bind(this, this._startAppSwitcher));
        Meta.keybindings_set_custom_handler('switch-windows-backward',
                                            Lang.bind(this, this._startAppSwitcher));
        Meta.keybindings_set_custom_handler('switch-group-backward',
                                            Lang.bind(this, this._startAppSwitcher));
        Meta.keybindings_set_custom_handler('switch-panels',
                                            Lang.bind(this, this._startA11ySwitcher));

        Main.overview.connect('showing', Lang.bind(this, function() {
            for (let i = 0; i < this._dimmedWindows.length; i++)
                this._undimWindow(this._dimmedWindows[i], true);
        }));
        Main.overview.connect('hiding', Lang.bind(this, function() {
            for (let i = 0; i < this._dimmedWindows.length; i++)
                this._dimWindow(this._dimmedWindows[i], true);
        }));

        global.screen.connect ("show-snap-osd", Lang.bind (this, this._showSnapOSD));
        global.screen.connect ("hide-snap-osd", Lang.bind (this, this._hideSnapOSD));
        global.screen.connect ("show-workspace-osd", Lang.bind (this, this.showWorkspaceOSD));
    },

    blockAnimations: function() {
        this._animationBlockCount++;
    },

    unblockAnimations: function() {
        this._animationBlockCount = Math.max(0, this._animationBlockCount - 1);
    },

    _shouldAnimate : function(actor) {
        if (Main.modalCount) {
            // system is in modal state
            return false;
        }
        if (Main.software_rendering)
            return false;
        if (!actor)
            return global.settings.get_boolean("desktop-effects");
        let type = actor.meta_window.get_window_type();
        if (type == Meta.WindowType.NORMAL) {
            return global.settings.get_boolean("desktop-effects");
        }
        if (type == Meta.WindowType.DIALOG || type == Meta.WindowType.MODAL_DIALOG) {
            return global.settings.get_boolean("desktop-effects-on-dialogs");
        }
        return false;
    },

    _startWindowEffect: function(cinnamonwm, name, actor, args, overwriteKey){
        let effect = this.effects[name];
        if(!this._shouldAnimate(actor)){
            cinnamonwm[effect.wmCompleteName](actor);
            return;
        }

        let key = "desktop-effects-" + (overwriteKey || effect.name);
        let type = global.settings.get_string(key + "-effect");

        //make sure to end a running effect
        if(actor.current_effect_name){
            this._endWindowEffect(cinnamonwm, actor.current_effect_name, actor);
        }
        this[effect.arrayName].push(actor);
        actor.current_effect_name = name;
        actor.orig_opacity = actor.opacity;
        actor.show();

        if(effect[type]){
            let time = global.settings.get_int(key + "-time") / 1000;
            let transition = global.settings.get_string(key + "-transition");

            effect[type](cinnamonwm, actor, time, transition, args);
        } else if(!overwriteKey) //when not unminimizing
            this._endWindowEffect(cinnamonwm, name, actor);
    },

    _endWindowEffect: function(cinnamonwm, name, actor){
        let effect = this.effects[name];
        //effect will be an instance of WindowEffects.Effect
        let idx = this[effect.arrayName].indexOf(actor);
        if(idx !== -1){
            this[effect.arrayName].splice(idx, 1);
            Tweener.removeTweens(actor);
            delete actor.current_effect_name;
            effect._end(actor);
            cinnamonwm[effect.wmCompleteName](actor);
        }
    },

    _killWindowEffects: function (cinnamonwm, actor) {
        for(let i in this._effects){
            this._endWindowEffect(cinnamonwm, i, actor);
        }
    },

    _minimizeWindow : function(cinnamonwm, actor) {
        Main.soundManager.play('minimize');

        // reset all cached values in case "traditional" is no longer in effect
        actor.get_meta_window()._cinnamonwm_has_origin = false;
        this._startWindowEffect(cinnamonwm, "minimize", actor);
    },

    _tileWindow : function (cinnamonwm, actor, targetX, targetY, targetWidth, targetHeight) {
        Main.soundManager.play('tile');

        this._startWindowEffect(cinnamonwm, "tile", actor, [targetX, targetY, targetWidth, targetHeight]);
    },

    _maximizeWindow : function(cinnamonwm, actor, targetX, targetY, targetWidth, targetHeight) {
        Main.soundManager.play('maximize');

        this._startWindowEffect(cinnamonwm, "maximize", actor, [targetX, targetY, targetWidth, targetHeight]);
    },

    _unmaximizeWindow : function(cinnamonwm, actor, targetX, targetY, targetWidth, targetHeight) {
        Main.soundManager.play('unmaximize');

        this._startWindowEffect(cinnamonwm, "unmaximize", actor, [targetX, targetY, targetWidth, targetHeight]);
    },

    _hasAttachedDialogs: function(window, ignoreWindow) {
        var count = 0;
        window.foreach_transient(function(win) {
            if (win != ignoreWindow && win.is_attached_dialog())
                count++;
            return false;
        });
        return count != 0;
    },

    _checkDimming: function(window, ignoreWindow) {
        let shouldDim = this._hasAttachedDialogs(window, ignoreWindow);

        if (shouldDim && !window._dimmed) {
            window._dimmed = true;
            this._dimmedWindows.push(window);
            if (!Main.overview.visible)
                this._dimWindow(window, true);
        } else if (!shouldDim && window._dimmed) {
            window._dimmed = false;
            this._dimmedWindows = this._dimmedWindows.filter(function(win) {
                                                                 return win != window;
                                                             });
            if (!Main.overview.visible)
                this._undimWindow(window, true);
        }
    },

    _dimWindow: function(window, animate) {
        let actor = window.get_compositor_private();
        if (!actor)
            return;

        let dimmer = getWindowDimmer(actor);
        let enabled = Meta.prefs_get_attach_modal_dialogs();
        dimmer.setEnabled(enabled);
        if (!enabled)
            return;

        if (animate) {
            Tweener.addTween(dimmer,
                             { dimFactor: 1.0,
                               time: DIM_TIME,
                               transition: 'linear'
                             });
        } else {
            getWindowDimmer(actor).dimFactor = 1.0;
        }
    },

    _undimWindow: function(window, animate) {
        let actor = window.get_compositor_private();
        if (!actor)
            return;

        let dimmer = getWindowDimmer(actor);
        let enabled = Meta.prefs_get_attach_modal_dialogs();
        dimmer.setEnabled(enabled);
        if (!enabled)
            return;

        if (animate) {
            Tweener.addTween(dimmer,
                             { dimFactor: 0.0,
                               time: UNDIM_TIME,
                               transition: 'linear'
                             });
        } else {
            getWindowDimmer(actor).dimFactor = 0.0;
        }
    },

    _mapWindow : function(cinnamonwm, actor) {
        actor._windowType = actor.meta_window.get_window_type();
        actor._notifyWindowTypeSignalId = actor.meta_window.connect('notify::window-type', Lang.bind(this, function () {
            let type = actor.meta_window.get_window_type();
            if (type == actor._windowType)
                return;
            if (type == Meta.WindowType.MODAL_DIALOG ||
                actor._windowType == Meta.WindowType.MODAL_DIALOG) {
                let parent = actor.get_meta_window().get_transient_for();
                if (parent)
                    this._checkDimming(parent);
            }

            actor._windowType = type;
        }));

        if (actor.get_meta_window()._cinnamonwm_has_origin === true) {
            try {
                this._startWindowEffect(cinnamonwm, "unminimize", actor, null, "minimize");
                return;
            } catch(e){
                //catch "no origin found"
            }
        } else if (actor.meta_window.get_window_type() == Meta.WindowType.NORMAL) {
            Main.soundManager.play('map');
        }
        this._startWindowEffect(cinnamonwm, "map", actor);
    },


    _destroyWindow : function(cinnamonwm, actor) {

        if (actor.meta_window.get_window_type() == Meta.WindowType.NORMAL) {
            Main.soundManager.play('close');
        }

        actor.orig_opacity = actor.opacity;

        let window = actor.meta_window;
        if (actor._notifyWindowTypeSignalId) {
            window.disconnect(actor._notifyWindowTypeSignalId);
            actor._notifyWindowTypeSignalId = 0;
        }
        if (window._dimmed) {
            this._dimmedWindows = this._dimmedWindows.filter(function(win) {
                                                                 return win != window;
                                                             });
        }

        if (window.minimized) {
            cinnamonwm.completed_destroy(actor);
            return;
        }

        this._startWindowEffect(cinnamonwm, "close", actor);
    },

    _switchWorkspace : function(cinnamonwm, from, to, direction) {
        if (!this._shouldAnimate()) {
            cinnamonwm.completed_switch_workspace();
            return;
        }

        let windows = global.get_window_actors();

        /* @direction is the direction that the "camera" moves, so the
         * screen contents have to move one screen's worth in the
         * opposite direction.
         */
        let xDest = 0, yDest = 0;

        if (direction == Meta.MotionDirection.UP ||
            direction == Meta.MotionDirection.UP_LEFT ||
            direction == Meta.MotionDirection.UP_RIGHT)
                yDest = global.screen_height;
        else if (direction == Meta.MotionDirection.DOWN ||
            direction == Meta.MotionDirection.DOWN_LEFT ||
            direction == Meta.MotionDirection.DOWN_RIGHT)
                yDest = -global.screen_height;

        if (direction == Meta.MotionDirection.LEFT ||
            direction == Meta.MotionDirection.UP_LEFT ||
            direction == Meta.MotionDirection.DOWN_LEFT)
                xDest = global.screen_width;
        else if (direction == Meta.MotionDirection.RIGHT ||
                 direction == Meta.MotionDirection.UP_RIGHT ||
                 direction == Meta.MotionDirection.DOWN_RIGHT)
                xDest = -global.screen_width;

        let switchData = {};
        this._switchData = switchData;
        switchData.inGroup = new Clutter.Group();
        switchData.outGroup = new Clutter.Group();
        switchData.windows = [];

        let wgroup = global.window_group;
        wgroup.add_actor(switchData.inGroup);
        wgroup.add_actor(switchData.outGroup);

        for (let i = 0; i < windows.length; i++) {
            let window = windows[i];

            if (!window.meta_window.showing_on_its_workspace())
                continue;

            if (window.get_workspace() == from) {
                switchData.windows.push({ window: window,
                                          parent: window.get_parent() });
                global.reparentActor(window, switchData.outGroup);
            } else if (window.get_workspace() == to) {
                switchData.windows.push({ window: window,
                                          parent: window.get_parent() });
                global.reparentActor(window, switchData.inGroup);
                window.show_all();
            }
        }

        switchData.inGroup.set_position(-xDest, -yDest);
        switchData.inGroup.raise_top();

        Tweener.addTween(switchData.outGroup,
                         { x: xDest,
                           y: yDest,
                           time: WINDOW_ANIMATION_TIME,
                           transition: 'easeOutQuad',
                           onComplete: this._switchWorkspaceDone,
                           onCompleteScope: this,
                           onCompleteParams: [cinnamonwm]
                         });
        Tweener.addTween(switchData.inGroup,
                         { x: 0,
                           y: 0,
                           time: WINDOW_ANIMATION_TIME,
                           transition: 'easeOutQuad'
                         });
    },

    _switchWorkspaceDone : function(cinnamonwm) {
        let switchData = this._switchData;
        if (!switchData)
            return;
        this._switchData = null;

        for (let i = 0; i < switchData.windows.length; i++) {
                let w = switchData.windows[i];
                if (w.window.is_destroyed()) // Window gone
                    continue;
                if (w.window.get_parent() == switchData.outGroup) {
                    global.reparentActor(w.window, w.parent);
                    w.window.hide();
                } else {
                    global.reparentActor(w.window, w.parent);
                }
        }
        Tweener.removeTweens(switchData.inGroup);
        Tweener.removeTweens(switchData.outGroup);
        switchData.inGroup.destroy();
        switchData.outGroup.destroy();

        cinnamonwm.completed_switch_workspace();
    },

    showWorkspaceOSD : function() {
        this._hideSnapOSD();
        this._hideWorkspaceOSD();
        if (global.settings.get_boolean("workspace-osd-visible")) {
            let current_workspace_index = global.screen.get_active_workspace_index();
            let monitor = Main.layoutManager.primaryMonitor;
            if (this._workspace_osd == null)
                this._workspace_osd = new St.Label({style_class:'workspace-osd'});
            this._workspace_osd.set_text(Main.getWorkspaceName(current_workspace_index));
            this._workspace_osd.set_opacity = 0;
            Main.layoutManager.addChrome(this._workspace_osd, { visibleInFullscreen: false, affectsInputRegion: false });
            let workspace_osd_x = global.settings.get_int("workspace-osd-x");
            let workspace_osd_y = global.settings.get_int("workspace-osd-y");
            /*
             * This aligns the osd edges to the minimum/maximum values from gsettings,
             * if those are selected to be used. For values in between minimum/maximum,
             * it shifts the osd by half of the percentage used of the overall space available
             * for display (100% - (left and right 'padding')).
             * The horizontal minimum/maximum values are 5% and 95%, resulting in 90% available for positioning
             * If the user choses 50% as osd position, these calculations result the osd being centered onscreen
             */
            let [minX, maxX, minY, maxY] = [5, 95, 5, 95];
            let delta = (workspace_osd_x - minX) / (maxX - minX);
            let x = Math.round((monitor.width * workspace_osd_x / 100) - (this._workspace_osd.width * delta));
            delta = (workspace_osd_y - minY) / (maxY - minY);
            let y = Math.round((monitor.height * workspace_osd_y / 100) - (this._workspace_osd.height * delta));
            this._workspace_osd.set_position(x, y);
            let duration = global.settings.get_int("workspace-osd-duration") / 1000;
            Tweener.addTween(this._workspace_osd, {   opacity: 255,
                                                         time: duration,
                                                   transition: 'linear',
                                                   onComplete: this._hideWorkspaceOSD,
                                              onCompleteScope: this });
        }
    },

    _hideWorkspaceOSD : function() {
        if (this._workspace_osd != null) {
            this._workspace_osd.hide();
            Main.layoutManager.removeChrome(this._workspace_osd);
            this._workspace_osd.destroy();
            this._workspace_osd = null;
        }
    },

    _showSnapOSD : function() {
        if (!global.settings.get_boolean("hide-snap-osd")) {
            if (this._snap_osd == null) {
                this._snap_osd = new St.BoxLayout({ vertical: true, style_class: "snap-osd" });
                let snap_info = new St.Label();
                let settings = new Gio.Settings({ schema: "org.cinnamon.muffin" });
                let mod = settings.get_string("snap-modifier");
                if (mod == "Super")
                    snap_info.set_text (_("Hold <Super> to enter snap mode"));
                else if (mod == "Alt")
                    snap_info.set_text (_("Hold <Alt> to enter snap mode"));
                else if (mod == "Control")
                    snap_info.set_text (_("Hold <Ctrl> to enter snap mode"));
                else if (mod == "Shift")
                    snap_info.set_text (_("Hold <Shift> to enter snap mode"));
                let flip_info = new St.Label();
                flip_info.set_text (_("Use the arrow keys to shift workspaces"));
                if (mod != "")
                    this._snap_osd.add (snap_info, { y_align: St.Align.START });
                this._snap_osd.add (flip_info, { y_align: St.Align.END });
                Main.layoutManager.addChrome(this._snap_osd, { visibleInFullscreen: false, affectsInputRegion: false});
            }
            this._snap_osd.set_opacity = 0;
            let monitor = Main.layoutManager.primaryMonitor;
            let workspace_osd_x = global.settings.get_int("workspace-osd-x");
            let workspace_osd_y = global.settings.get_int("workspace-osd-y");
            let [minX, maxX, minY, maxY] = [5, 95, 5, 95];
            let delta = (workspace_osd_x - minX) / (maxX - minX);
            let x = Math.round((monitor.width * workspace_osd_x / 100) - (this._snap_osd.width * delta));
            delta = (workspace_osd_y - minY) / (maxY - minY);
            let y = Math.round((monitor.height * workspace_osd_y / 100) - (this._snap_osd.height * delta));
            this._snap_osd.set_position(x, y);
            this._snap_osd.show_all();
        }
    },

    _hideSnapOSD : function() {
        if (this._snap_osd != null) {
            this._snap_osd.hide();
            Main.layoutManager.removeChrome(this._snap_osd);
            this._snap_osd.destroy();
            this._snap_osd = null;
        }
    },

    _createAppSwitcher : function(binding) {
        if (AppSwitcher.getWindowsForBinding(binding).length == 0)
            return;
        let style = global.settings.get_string("alttab-switcher-style");
        if(style == 'coverflow')
            new CoverflowSwitcher.CoverflowSwitcher(binding);
        else if(style == 'timeline')
            new TimelineSwitcher.TimelineSwitcher(binding);
        else
            new ClassicSwitcher.ClassicSwitcher(binding);
    },

    _startAppSwitcher : function(display, screen, window, binding) {
        this._createAppSwitcher(binding);
    },

    _startA11ySwitcher : function(display, screen, window, binding) {
        this._createAppSwitcher(binding);
    },

    _shiftWindowToWorkspace : function(window, direction) {
        if (window.get_window_type() === Meta.WindowType.DESKTOP) {
            return;
        }
        let workspace = global.screen.get_active_workspace().get_neighbor(direction);
        if (workspace != global.screen.get_active_workspace()) {
            window.change_workspace(workspace);
            workspace.activate(global.get_current_time());
            this.showWorkspaceOSD();
            Mainloop.idle_add(Lang.bind(this, function() {
                // Unless this is done a bit later, window is sometimes not activated
                if (window.get_workspace() == global.screen.get_active_workspace()) {
                    window.activate(global.get_current_time());
                }
            }));
        }
    },

    _moveWindowToWorkspaceLeft : function(display, screen, window, binding) {
        this._shiftWindowToWorkspace(window, Meta.MotionDirection.LEFT);
    },

    _moveWindowToWorkspaceRight : function(display, screen, window, binding) {
        this._shiftWindowToWorkspace(window, Meta.MotionDirection.RIGHT);
    },

    _showWorkspaceSwitcher : function(display, screen, window, binding) {
        if (binding.get_name() == 'switch-to-workspace-up') {
            Main.expo.toggle();
            return;
        }
        if (binding.get_name() == 'switch-to-workspace-down') {
            Main.overview.toggle();
            return;
        }

        if (screen.n_workspaces == 1)
            return;

        let current_workspace_index = global.screen.get_active_workspace_index();
        if (binding.get_name() == 'switch-to-workspace-left') {
           this.actionMoveWorkspaceLeft();
           if (current_workspace_index !== global.screen.get_active_workspace_index()) {
                this.showWorkspaceOSD();
           }
        }
        else if (binding.get_name() == 'switch-to-workspace-right') {
           this.actionMoveWorkspaceRight();
           if (current_workspace_index !== global.screen.get_active_workspace_index()) {
                this.showWorkspaceOSD();
           }
        }
    },

    actionMoveWorkspaceLeft: function() {
        var active = global.screen.get_active_workspace();
        var neighbour = active.get_neighbor(Meta.MotionDirection.LEFT)
        if (active != neighbour) {
            Main.soundManager.play('switch');
            neighbour.activate(global.get_current_time());
        }
    },

    actionMoveWorkspaceRight: function() {
        var active = global.screen.get_active_workspace();
        var neighbour = active.get_neighbor(Meta.MotionDirection.RIGHT)
        if (active != neighbour) {
            Main.soundManager.play('switch');
            neighbour.activate(global.get_current_time());
        }
    },

    actionMoveWorkspaceUp: function() {
        global.screen.get_active_workspace().get_neighbor(Meta.MotionDirection.UP).activate(global.get_current_time());
    },

    actionMoveWorkspaceDown: function() {
        global.screen.get_active_workspace().get_neighbor(Meta.MotionDirection.DOWN).activate(global.get_current_time());
    },

    actionFlipWorkspaceLeft: function() {
        var active = global.screen.get_active_workspace();
        var neighbor = active.get_neighbor(Meta.MotionDirection.LEFT);
        if (active != neighbor) {
            neighbor.activate(global.get_current_time());
            let [x, y, mods] = global.get_pointer();
            global.set_pointer(global.screen_width - 10, y);
        }
    },

    actionFlipWorkspaceRight: function() {
        var active = global.screen.get_active_workspace();
        var neighbor = active.get_neighbor(Meta.MotionDirection.RIGHT);
        if (active != neighbor) {
            neighbor.activate(global.get_current_time());
            let [x, y, mods] = global.get_pointer();
            global.set_pointer(10, y);
        }
    }
};
