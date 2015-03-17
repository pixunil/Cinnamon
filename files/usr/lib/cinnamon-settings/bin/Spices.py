try:
    from SettingsWidgets import rec_mkdir
    import gettext
    from gi.repository import Gio, Gtk, GObject, Gdk, GdkPixbuf, GLib
    # WebKit requires gir1.2-javascriptcoregtk-3.0 and gir1.2-webkit-3.0
    # try:
    #     from gi.repository import WebKit
    #     HAS_WEBKIT=True
    # except:
    #     HAS_WEBKIT=False
    #     print "WebKit not found on this system. These packages are needed for adding spices:"
    #     print "  gir1.2-javascriptcoregtk-3.0"
    #     print "  gir1.2-webkit-3.0"
    import locale
    import tempfile
    import os
    import sys
    import time
    import urllib2
    import zipfile
    import string
    import shutil
    import cgi
    import subprocess
    import threading
except Exception, detail:
    print detail
    sys.exit(1)

try:
    import json
except ImportError:
    import simplejson as json

home = os.path.expanduser("~")
locale_inst = '%s/.local/share/locale' % home
settings_dir = '%s/.cinnamon/configs/' % home

URL_SPICES_HOME = "http://cinnamon-spices.linuxmint.com"
URL_SPICES_APPLET_LIST = URL_SPICES_HOME + "/json/applets.json"
URL_SPICES_THEME_LIST = URL_SPICES_HOME + "/json/themes.json"
URL_SPICES_DESKLET_LIST = URL_SPICES_HOME + "/json/desklets.json"
URL_SPICES_EXTENSION_LIST = URL_SPICES_HOME + "/json/extensions.json"

ABORT_NONE = 0
ABORT_ERROR = 1
ABORT_USER = 2

def removeEmptyFolders(path):
    if not os.path.isdir(path):
        return

    # remove empty subfolders
    files = os.listdir(path)
    if len(files):
        for f in files:
            fullpath = os.path.join(path, f)
            if os.path.isdir(fullpath):
                removeEmptyFolders(fullpath)

    # if folder empty, delete it
    files = os.listdir(path)
    if len(files) == 0:
        print "Removing empty folder:", path
        os.rmdir(path)

class Spice_Harvester(Gtk.HBox):
    def __init__(self, collection_type):
        super(Spice_Harvester, self).__init__()

        self.collection_type = collection_type
        self.cache_folder = self.get_cache_folder()
        self.install_folder = self.get_install_folder()
        self.index_cache = {}
        self.error = None
        self.themes = collection_type == "theme"
        self.threads = []

        if not os.path.exists(os.path.join(self.cache_folder, "index.json")):
            self.has_cache = False
        else:
            self.has_cache = True

        self.bar = Gtk.ProgressBar()
        self.bar.set_show_text(True)
        self.label = Gtk.Label()

        self.pack_start(self.bar, False, False, 2)
        self.pack_start(self.label, True, False, 2)
        self.connect("show", self.maybe_hide)

    def maybe_hide(self, widget):
        if len(self.threads) == 0:
            self.hide()

    def get_webkit_enabled(self):
        return HAS_WEBKIT

    def close_select_detail(self):
        self.spiceDetail.hide()
        if callable(self.on_detail_select):
            self.on_detail_select(self)

    def on_close_detail(self, *args):
        self.close_detail()
        return True

    def close_detail(self):
        self.spiceDetail.hide()
        if hasattr(self, 'on_detail_close') and callable(self.on_detail_close):
            self.on_detail_close(self)

    def show_detail(self, uuid, onSelect=None, onClose=None):        
        self.on_detail_select = onSelect
        self.on_detail_close = onClose

        if not self.has_cache:
            self.refresh_cache(False)
        elif len(self.index_cache) == 0:
            self.load_cache()

        if uuid not in self.index_cache:
            self.load(lambda x: self.show_detail(uuid))
            return

        appletData = self.index_cache[uuid] 

        # Browsing the info within the app would be great (ala mintinstall) but until it is fully ready 
        # and it gives a better experience (layout, comments, reviewing) than 
        # browsing online we will open the link with an external browser 
        os.system("xdg-open '%s/%ss/view/%s'" % (URL_SPICES_HOME, self.collection_type, appletData['spices-id']))
        return
        
        screenshot_filename = os.path.basename(appletData['screenshot'])
        screenshot_path = os.path.join(self.get_cache_folder(), screenshot_filename)
        appletData['screenshot_path'] = screenshot_path
        appletData['screenshot_filename'] = screenshot_filename

        if not os.path.exists(screenshot_path):
            f = open(screenshot_path, 'w')
            self.download_url = URL_SPICES_HOME + appletData['screenshot']
            self.download_with_progressbar(f, screenshot_path, _("Downloading screenshot"), False)

        template = open(os.path.realpath(os.path.dirname(os.path.abspath(__file__)) + "/../data/spices/applet-detail.html")).read()
        subs = {}
        subs['appletData'] = json.dumps(appletData, sort_keys=False, indent=3)
        html = string.Template(template).safe_substitute(subs)

        # Prevent flashing previously viewed
        self._sigLoadFinished = self.browser.connect("document-load-finished", lambda x, y: self.real_show_detail())
        self.browser.load_html_string(html, "file:///")

    def real_show_detail(self):
        self.browser.show()
        self.spiceDetail.show()
        self.browser.disconnect(self._sigLoadFinished)

    def browser_title_changed(self, view, frame, title):
        if title.startswith("nop"):
            return
        elif title.startswith("install:"):
            uuid = title.split(':')[1]
            #self.install(uuid)
        elif title.startswith("uninstall:"):
            uuid = title.split(':')[1]
            #self.uninstall(uuid, '')
        return

    def browser_console_message(self, view, msg, line, sourceid):
        return
        #print msg

    def get_index_url(self):
        if self.collection_type == 'applet':
            return URL_SPICES_APPLET_LIST
        elif self.collection_type == 'extension':
            return URL_SPICES_EXTENSION_LIST
        elif self.collection_type == 'theme':
            return URL_SPICES_THEME_LIST
        elif self.collection_type == 'desklet':
            return URL_SPICES_DESKLET_LIST
        else:
            return False

    def get_cache_folder(self):
        cache_folder = "%s/.cinnamon/spices.cache/%s/" % (home, self.collection_type)

        if not os.path.exists(cache_folder):
            rec_mkdir(cache_folder)
        return cache_folder

    def get_install_folder(self):
        if self.collection_type in ['applet','desklet','extension']:
            install_folder = '%s/.local/share/cinnamon/%ss/' % (home, self.collection_type)
        elif self.collection_type == 'theme':
            install_folder = '%s/.themes/' % (home)

        return install_folder

    def start_thread(self, thread_class, callbacks, *args):
        thread = thread_class(self, args)
        thread.callbacks = callbacks
        thread.start()
        self.threads.insert(0, thread)
        if len(self.threads) == 1:
            GLib.timeout_add(100, self.check_loading_progress)
            self.show()

    def check_loading_progress(self):
        thread = self.threads[0]
        data = thread.data

        if "error" in data:
            self.errorMessage(*data["error"])
            del data["error"]

        self.bar.set_text(data["bar-text"])

        if data["bar-fraction"] == -1:
            self.bar.set_pulse_step(0.1)
            self.bar.pulse()
        else:
            self.bar.set_fraction(data["bar-fraction"])

        self.label.set_text(data["label-text"])

        for name, args in thread.callback_data.items():
            thread.callbacks[name](*args)
        thread.callback_data = {}

        alive = thread.is_alive()
        if not alive:
            self.threads.pop(0)
        if len(self.threads):
            return True
        else:
            self.hide()
            return False

    def load(self, on_done, on_update, force=False):
        if self.has_cache and not force:
            self.start_thread(LoadCacheThread, {"cache-loaded": on_done})
        else:
            self.start_thread(RefreshCacheThread, {"cache-loaded": on_done, "icon-updated": on_update})

    def install(self, install_list=[], onFinished=None):
        self.start_thread(InstallThread, {"install-finished": onFinished}, install_list)

    def uninstall(self, uuid, name, schema_filename, onFinished=None):
        self.start_thread(UninstallThread, {"uninstall-finished": onFinished}, uuid, name, schema_filename)

    def on_abort_clicked(self, button):
        self.abort_download = ABORT_USER
        self.hide()
        return

    def on_refresh_clicked(self):
        self.load_index()

    def scrubConfigDirs(self, enabled_list):
        active_list = {}
        for enabled in enabled_list:
            if self.collection_type == "applet":
                panel, align, order, uuid, id = enabled.split(":")
            elif self.collection_type == "desklet":
                uuid, id, x, y = enabled.split(":")
            else:
                uuid = enabled
                id = 0
            if uuid not in active_list:
                id_list = []
                active_list[uuid] = id_list
                active_list[uuid].append(id)
            else:
                active_list[uuid].append(id)

        for uuid in active_list.keys():
            if (os.path.exists(os.path.join(settings_dir, uuid))):
                dir_list = os.listdir(os.path.join(settings_dir, uuid))
                fn = str(uuid) + ".json"
                if fn in dir_list and len(dir_list) == 1:
                    dir_list.remove(fn)
                for id in active_list[uuid]:
                    fn = str(id) + ".json"
                    if fn in dir_list:
                        dir_list.remove(fn)
                for jetsam in dir_list:
                    try:
                        os.remove(os.path.join(settings_dir, uuid, jetsam))
                    except:
                        pass

    def on_progress_close(self, widget, event):
        self.abort_download = True
        return widget.hide_on_delete()

    def errorMessage(self, msg, detail = None):
        dialog = Gtk.MessageDialog(transient_for = None,
                                   modal = True,
                                   message_type = Gtk.MessageType.ERROR,
                                   buttons = Gtk.ButtonsType.OK)
        markup = msg
        if detail is not None:
            markup += _("\n\nDetails:  %s") % (str(detail))
        esc = cgi.escape(markup)
        dialog.set_markup(esc)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

class Thread(threading.Thread):
    abort_download = ABORT_NONE

    def __init__(self, harvester, args):
        super(Thread, self).__init__()

        self.harvester = harvester
        self.args = args
        self.data = {
            "bar-text": "",
            "bar-fraction": -1,
            "label-text": "",
            "total-files": 0,
            "current-file": 0
        }
        self.callback_data = {}

    def run(self):
        self.action(self.harvester, *self.args)

    def action(self, harvester):
        pass

    def sanitize_thumb(self, basename):
        return basename.replace("jpg", "png").replace("JPG", "png").replace("PNG", "png")

    def download(self, url, outfile):
        try:
            self.url_retrieve(url, outfile)
        except KeyboardInterrupt:
            raise
            try:
                os.remove(outfile)
            except OSError:
                pass
            if self.abort_download == ABORT_ERROR:
                self.data["error"] = (_("An error occurred while trying to access the server.  Please try again in a little while."), self.error)
            raise Exception(_("Download aborted."))

        return outfile

    def url_retrieve(self, url, outfile):
        #Like the one in urllib. Unlike urllib.retrieve url_retrieve
        #can be interrupted. KeyboardInterrupt exception is rasied when
        #interrupted.
        count = 0
        blockSize = 1024 * 8
        try:
            urlobj = urllib2.urlopen(url)
        except Exception, detail:
            self.abort_download = ABORT_ERROR
            self.error = detail
            raise KeyboardInterrupt

        totalSize = int(urlobj.info()['content-length'])

        f = open(outfile, "w")

        try:
            while self.abort_download == ABORT_NONE:
                data = urlobj.read(blockSize)
                count += 1
                if not data:
                    break
                f.write(data)
                self.reporthook(count, blockSize, totalSize)
        except KeyboardInterrupt:
            f.close()
            self.abort_download = ABORT_USER

        if self.abort_download > ABORT_NONE:
            raise KeyboardInterrupt

        del urlobj
        f.close()

    def reporthook(self, count, blockSize, totalSize):
        if self.data["total-files"] > 1:
            fraction = (float(self.data["current-file"]) / float(self.data["total-files"]))
            self.data["bar-text"] = "%d%% - %d / %d files" % (fraction * 100, self.data["current-file"], self.data["total-files"])
        else:
            fraction = count * blockSize / float((totalSize / blockSize + 1) * blockSize)
            self.data["bar-text"] = "%d%%" % (fraction * 100)

        if fraction >= 0:
            self.data["bar-fraction"] = fraction
        else:
            self.data["bar-fraction"] = -1

class LoadCacheThread(Thread):
    def action(self, harvester):
        filename = os.path.join(harvester.cache_folder, "index.json")
        f = open(filename, "r")
        try:
            harvester.index_cache = json.load(f)
            self.callback_data["cache-loaded"] = ()
        except ValueError, detail:
            try:
                os.remove(filename)
            except:
                pass
            self.data["error"] = (_("Something went wrong with the spices download.  Please try refreshing the list again."), str(detail))

class LoadAssestsThread(Thread):
    def action(self, harvester):
        self.data["label-text"] = _("Refreshing cache...")

        needs_download = []
        used_thumbs = []

        uuids = harvester.index_cache.keys()

        for uuid in uuids:
            if not harvester.themes:
                icon_basename = os.path.basename(harvester.index_cache[uuid]['icon'])
                icon_path = os.path.join(harvester.cache_folder, icon_basename)
                used_thumbs.append(icon_basename)
            else:
                icon_basename = self.sanitize_thumb(os.path.basename(harvester.index_cache[uuid]['screenshot']))
                icon_path = os.path.join(harvester.cache_folder, icon_basename)
                used_thumbs.append(icon_basename)

            harvester.index_cache[uuid]["icon_filename"] = icon_basename
            harvester.index_cache[uuid]["icon_path"] = icon_path

            if not os.path.isfile(icon_path):
                needs_download.append(uuid)

        self.data["total-files"] = len(needs_download)

        for uuid in needs_download:
            if self.abort_download > ABORT_NONE:
                return

            #self.progress_bar_pulse()
            self.data["current-file"] += 1
            if not harvester.themes:
                url = URL_SPICES_HOME + harvester.index_cache[uuid]['icon']
            else:
                url = URL_SPICES_HOME + "/uploads/themes/thumbs/" + harvester.index_cache[uuid]['icon_filename']
            valid = True
            try:
                urllib2.urlopen(url).getcode()
            except:
                valid = False
            if valid:
                self.download(url, harvester.index_cache[uuid]["icon_path"])
                self.callback_data["icon-updated"] = (uuid,)

        # Cleanup obsolete thumbs
        trash = []
        flist = os.listdir(harvester.cache_folder)
        for f in flist:
            if f not in used_thumbs and f != "index.json":
                trash.append(f)
        for t in trash:
            try:
                os.remove(os.path.join(harvester.cache_folder, t))
            except:
                pass

class RefreshCacheThread(LoadCacheThread, LoadAssestsThread):
    def action(self, harvester):
        self.data["label-text"] = _("Refreshing index...")

        url = harvester.get_index_url()
        filename = os.path.join(harvester.cache_folder, "index.json")
        self.download(url, filename)

        LoadCacheThread.action(self, harvester)
        LoadAssestsThread.action(self, harvester)

class InstallThread(Thread):
    def action(self, harvester, install_list):
        need_restart = False
        for uuid, is_update, is_active in install_list:
            print uuid
            success = self.install(harvester, harvester.index_cache[uuid], uuid)
            need_restart = need_restart or (is_update and is_active and success)

        self.callback_data["install-finished"] = (need_restart,)

    def install(self, harvester, spice, uuid):
        title = spice["name"]

        self.data["label-text"] = _("Installing %s...") % title

        edited_date = spice['last_edited']

        if not harvester.themes:
            fd, filename = tempfile.mkstemp()
            dirname = tempfile.mkdtemp()
            try:
                self.download(URL_SPICES_HOME + spice['file'], filename)
                dest = os.path.join(harvester.install_folder, uuid)
                schema_filename = ""
                zip = zipfile.ZipFile(filename)
                zip.extractall(dirname, self.get_members(zip))
                for file in self.get_members(zip):
                    if not file.filename.endswith('/') and ((file.external_attr >> 16L) & 0o755) == 0o755:
                        os.chmod(os.path.join(dirname, file.filename), 0o755)
                    elif file.filename[:3] == 'po/':
                        parts = os.path.splitext(file.filename)
                        if parts[1] == '.po':
                           this_locale_dir = os.path.join(locale_inst, parts[0][3:], 'LC_MESSAGES')
                           self.data["label-text"] = _("Installing translations for %s...") % title
                           rec_mkdir(this_locale_dir)
                           #print "/usr/bin/msgfmt -c %s -o %s" % (os.path.join(dest, file.filename), os.path.join(this_locale_dir, '%s.mo' % uuid))
                           subprocess.call(["msgfmt", "-c", os.path.join(dirname, file.filename), "-o", os.path.join(this_locale_dir, '%s.mo' % uuid)])
                           self.data["label-text"] = _("Installing %s...") % title
                    elif "gschema.xml" in file.filename:
                        sentence = _("Please enter your password to install the required settings schema for %s") % uuid
                        if os.path.exists("/usr/bin/gksu") and os.path.exists("/usr/lib/cinnamon-settings/bin/installSchema.py"):
                            launcher = "gksu  --message \"<b>%s</b>\"" % sentence
                            tool = "/usr/lib/cinnamon-settings/bin/installSchema.py %s" % (os.path.join(dirname, file.filename))
                            command = "%s %s" % (launcher, tool)
                            os.system(command)
                            schema_filename = file.filename
                        else:
                            self.data["error"] = (_("Could not install the settings schema for %s.  You will have to perform this step yourself.") % uuid, None)
                file = open(os.path.join(dirname, "metadata.json"), 'r')
                raw_meta = file.read()
                file.close()
                md = json.loads(raw_meta)
                md["last-edited"] = edited_date
                if schema_filename != "":
                    md["schema-file"] = schema_filename
                raw_meta = json.dumps(md, indent=4)
                file = open(os.path.join(dirname, "metadata.json"), 'w+')
                file.write(raw_meta)
                file.close()
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(dirname, dest)
                shutil.rmtree(dirname)
                os.remove(filename)

            except Exception, detail:
                try:
                    shutil.rmtree(dirname)
                    os.remove(filename)
                except:
                    pass
                if not self.abort_download:
                    self.data["error"] = (_("An error occurred during installation or updating.  You may wish to report this incident to the developer of %s.\n\nIf this was an update, the previous installation is unchanged") % uuid, str(detail))
                return False
        else:
            fd, filename = tempfile.mkstemp()
            dirname = tempfile.mkdtemp()
            try:
                self.download(URL_SPICES_HOME + spice['file'], filename)
                dest = harvester.install_folder
                zip = zipfile.ZipFile(filename)
                zip.extractall(dirname)

                # Check dir name - it may or may not be the same as the theme name from our spices data
                # Regardless, this will end up being the installed theme name, whether it matched or not
                temp_path = os.path.join(dirname, title)
                if not os.path.exists(temp_path):
                    title = os.listdir(dirname)[0] # We assume only a single folder, the theme name
                    temp_path = os.path.join(dirname, title)

                # Test for correct folder structure - look for cinnamon.css
                file = open(os.path.join(temp_path, "cinnamon", "cinnamon.css"), 'r')
                file.close()

                md = {}
                md["last-edited"] = edited_date
                md["uuid"] = uuid
                raw_meta = json.dumps(md, indent=4)
                file = open(os.path.join(temp_path, "cinnamon", "metadata.json"), 'w+')
                file.write(raw_meta)
                file.close()
                final_path = os.path.join(dest, title)
                if os.path.exists(final_path):
                    shutil.rmtree(final_path)
                shutil.copytree(temp_path, final_path)
                shutil.rmtree(dirname)
                os.remove(filename)

            except Exception, detail:
                try:
                    shutil.rmtree(dirname)
                    os.remove(filename)
                except:
                    pass
                if not self.abort_download:
                    self.data["error"] = (_("An error occurred during installation or updating.  You may wish to report this incident to the developer of %s.\n\nIf this was an update, the previous installation is unchanged") % title, str(detail))
                return False
        return True

    def get_members(self, zip):
        parts = []
        for name in zip.namelist():
            if not name.endswith('/'):
                parts.append(name.split('/')[:-1])
        prefix = os.path.commonprefix(parts) or ''
        if prefix:
            prefix = '/'.join(prefix) + '/'
        offset = len(prefix)
        for zipinfo in zip.infolist():
            name = zipinfo.filename
            if len(name) > offset:
                zipinfo.filename = name[offset:]
                yield zipinfo

class UninstallThread(Thread):
    def action(self, harvester, uuid, name, schema_filename):
        self.data["label-text"] = _("Uninstalling %s...") % name
        try:
            if not harvester.themes:
                if schema_filename != "":
                    sentence = _("Please enter your password to remove the settings schema for %s") % (uuid)
                    if os.path.exists("/usr/bin/gksu") and os.path.exists("/usr/lib/cinnamon-settings/bin/removeSchema.py"):
                        launcher = "gksu  --message \"<b>%s</b>\"" % sentence
                        tool = "/usr/lib/cinnamon-settings/bin/removeSchema.py %s" % (schema_filename)
                        command = "%s %s" % (launcher, tool)
                        os.system(command)
                    else:
                        self.data["error"] = (_("Could not remove the settings schema for %s.  You will have to perform this step yourself.  This is not a critical error.") % (uuid), None)
                shutil.rmtree(os.path.join(harvester.install_folder, uuid))

                # Uninstall spice localization files, if any
                if os.path.exists(locale_inst):
                    i19_folders = os.listdir(locale_inst)
                    for i19_folder in i19_folders:
                        if os.path.isfile(os.path.join(locale_inst, i19_folder, 'LC_MESSAGES', "%s.mo" % uuid)):
                            os.remove(os.path.join(locale_inst, i19_folder, 'LC_MESSAGES', "%s.mo" % uuid))
                        # Clean-up this locale folder
                        removeEmptyFolders(os.path.join(locale_inst, i19_folder))

                # Uninstall settings file, if any
                if os.path.exists(os.path.join(settings_dir, uuid)):
                    shutil.rmtree(os.path.join(settings_dir, uuid))
            else:
                shutil.rmtree(os.path.join(harvester.install_folder, name))
        except Exception, detail:
            self.data["error"] = (_("Problem uninstalling %s.  You may need to manually remove it.") % uuid, detail)

        self.callback_data["uninstall-finished"] = ()

