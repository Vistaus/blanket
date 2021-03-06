# Copyright 2020 Rafael Mardojai CM
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstPlayer', '1.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')

from gettext import gettext as _
from gi.repository import GLib, Gst, Gdk, Gio, Gtk, Handy
# Init GStreamer
Gst.init(None)

from blanket.mpris import MPRIS
from blanket.sound import MainPlayer
from blanket.sounds_settings import SoundsSettings
from blanket.window import BlanketWindow
from blanket.preferences import PreferencesWindow
from blanket.about import AboutDialog


class Application(Gtk.Application):
    def __init__(self, version):
        super().__init__(application_id='com.rafaelmardojai.Blanket',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        GLib.set_application_name(_('Blanket'))
        GLib.set_prgname('com.rafaelmardojai.Blanket')
        GLib.setenv('PULSE_PROP_application.icon_name',
                    'com.rafaelmardojai.Blanket-symbolic', True)
        # Connect app shutdown signal
        self.connect('shutdown', self._on_shutdown)

        # Add --hidden command line option
        self.add_main_option('hidden', b'h', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, 'Start window hidden', None)
        # App window
        self.window = None
        self.window_hidden = False
        # App version
        self.version = version

        # Settings
        self.settings = Gio.Settings.new('com.rafaelmardojai.Blanket')
        self.sounds_settings = SoundsSettings(self.settings)
        # Saved playing state
        self.volume = self.settings.get_double('volume')
        self.playing = self.settings.get_boolean('playing')

        # App main player
        self.mainplayer = MainPlayer()
        # Load saved props
        self.mainplayer.set_property('volume', self.volume)
        self.mainplayer.set_property('playing', self.playing)

        # Start MPRIS server
        MPRIS(self)

    def do_startup(self):
        # Startup application
        Gtk.Application.do_startup(self)
        self.setup_actions()
        self.load_css()

        # Init Handy
        Handy.init()

    def setup_actions(self):
        actions = [
            {
                'name'  : 'open',
                'func'  : self.on_open,
                'accels': ['<Ctl>o']
            },
            {
                'name'  : 'playpause',
                'func'  : self.on_playpause,
                'accels': ['<Ctl>m', 'space']
            },
            {
                'name'  : 'background-playback',
                'func'  : self.on_background,
                'state' : True
            },
            {
                'name'  : 'preferences',
                'func'  : self.on_preferences
            },
            {
                'name'  : 'shortcuts',
                'func'  : self.on_shortcuts
            },
            {
                'name'  : 'about',
                'func'  : self.on_about
            },
            {
                'name'  : 'close',
                'func'  : self.on_close,
                'accels': ['<Ctl>w']
            },
            {
                'name'  : 'quit',
                'func'  : self.on_quit,
                'accels': ['<Ctl>q']
            }
        ]

        for a in actions:
            if 'state' in a:
                action = Gio.SimpleAction.new_stateful(
                    a['name'], None, self.settings.get_value(a['name']))
                action.connect('change-state', a['func'])
            else:
                action = Gio.SimpleAction.new(a['name'], None)
                action.connect('activate', a['func'])

            self.add_action(action)

            if 'accels' in a:
                self.set_accels_for_action('app.' + a['name'], a['accels'])

    def load_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/com/rafaelmardojai/Blanket/style.css')
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def do_activate(self):
        self.window = self.props.active_window
        if not self.window:
            self.window = BlanketWindow(self.mainplayer, self.settings,
                                        self.sounds_settings, application=self)

        if self.window_hidden:
            self.window.hide()
            self.window_hidden = False
        else:
            self.window.present()

        # Update window elements to saved playing state
        self.window.update_playing_ui(self.playing)
        # Connect window delete-event signal to _on_window_delete
        self.window.connect('delete-event', self._on_window_delete)

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        options = options.end().unpack()

        if 'hidden' in options and self.window is None:
            self.window_hidden = True

        self.activate()
        return 0

    def on_open(self, action, param):
        self.window.open_audio()

    def on_playpause(self, action=None, param=None):
        # Reverse self.playing bool value
        self.playing = False if self.playing else True

        # Change mainplayer playing
        self.mainplayer.set_property('playing', self.playing)

        # Update window elements to new playing state
        self.window.update_playing_ui(self.playing)

    def on_background(self, action, value):
        action.set_state(value)
        self.settings.set_boolean('background-playback', value)
        if value:
            self.window.quit_revealer.set_reveal_child(True)
        else:
            self.window.quit_revealer.set_reveal_child(False)

    def on_preferences(self, action, param):
        window = PreferencesWindow(self.window, self.settings)
        window.set_transient_for(self.window)
        window.set_modal(True)
        window.present()

    def on_shortcuts(self, action, param):
        window = Gtk.Builder.new_from_resource(
            '/com/rafaelmardojai/Blanket/shortcuts.ui'
        ).get_object('shortcuts')
        window.set_transient_for(self.window)
        window.props.section_name = 'shortcuts'
        window.set_modal(True)
        window.present()

    def on_about(self, action, param):
        dialog = AboutDialog(self.version)
        dialog.set_transient_for(self.window)
        dialog.set_modal(True)
        dialog.present()

    def on_close(self, action, param):
        self.window.close()

    def on_quit(self, action, param):
        self.quit()

    def _save_settings(self):
        # Save scroll position
        scroll_position = self.window.vscroll.get_value()
        self.settings.set_double('scroll-position', scroll_position)

        # Save mainplayer volume
        volume = self.mainplayer.get_property('volume')
        self.settings.set_double('volume', volume)
        # Save mainplayer playing state
        playing = self.mainplayer.get_property('playing')
        self.settings.set_boolean('playing', playing)

        # Save sounds settings
        self.sounds_settings.save_all()

    def _on_window_delete(self, widget, event):
        background = self.settings.get_value('background-playback')

        if background:
            self._save_settings() # Save settings
            return widget.hide_on_delete()
        else:
            self.quit_from_window = True
            self.quit()

    def _on_shutdown(self, _app):
        self._save_settings()

def main(version):
    app = Application(version)
    return app.run(sys.argv)
