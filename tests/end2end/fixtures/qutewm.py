# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Daniel Schadt
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""qutewm - a simple window manager for qutebrowser tests.

Usage:
    DISPLAY=:n python qutewm.py -- [options]

    Where n is the display you want to run qutewm on.

Available options:
    --help: Show this help.
    --debug: Show debugging information.
    --repl: Also start a repl in a separate thread (useful for debugging).

Available keybindings:
    Alt + F1 - cycle though all windows
"""

import sys
import logging

from Xlib.display import Display
from Xlib import X, XK, protocol, Xatom


logging.basicConfig(
    style='{',
    format='{asctime} {name:10} {levelname:10} {module}:{funcName} {message}',
    level=logging.INFO,
)
log = logging.getLogger('qutewm')


class QuteWM:

    """Main class for the qutewm window manager.

    Attributes:
        dpy: The Display.
        dimensions: The screen's dimensions (width, height).
        windows: A list of all managed windows in mapping order.
        window_stack: A list of all windows in stack order.
        root: The root window.
        support_window: The window for the _NET_SUPPORTING_WM_CHECK.
    """

    WM_NAME = 'qutewm'

    def __init__(self):
        log.info("initializing")
        self._handlers = {
            X.MapNotify: self.on_MapNotify,
            X.UnmapNotify: self.on_UnmapNotify,
            X.KeyPress: self.on_KeyPress,
            X.ClientMessage: self.on_ClientMessage,
        }
        self.dpy = Display()

        screen_width = self.dpy.screen().width_in_pixels
        screen_height = self.dpy.screen().height_in_pixels
        self.dimensions = (screen_width, screen_height)

        self.root = self.dpy.screen().root
        self.support_window = None
        self.windows = []
        self.window_stack = []

        self.root.change_attributes(event_mask=X.SubstructureNotifyMask)
        self.root.grab_key(
            self.dpy.keysym_to_keycode(XK.string_to_keysym("F1")),
            X.Mod1Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

        self.ATOM_ACTIVE_WINDOW = self.dpy.get_atom('_NET_ACTIVE_WINDOW')

        self._set_supported_attribute()
        self._set_supporting_wm_check()


    def _set_supported_attribute(self):
        """Set the _NET_SUPPORTED attribute on the root window."""
        attributes = [
            '_NET_SUPPORTED',
            '_NET_ACTIVE_WINDOW',
            '_NET_CLIENT_LIST',
        ]
        self.root.change_property(
            self.dpy.get_atom('_NET_SUPPORTED'),
            Xatom.ATOM,
            32,
            [self.dpy.get_atom(x) for x in attributes],
        )


    def _set_supporting_wm_check(self):
        """Create and set a window for _NET_SUPPORTING_WM_CHECK."""
        self.support_window = self.root.create_window(
            0, 0, 10, 10, 0, self.dpy.screen().root_depth)

        for window in [self.root, self.support_window]:
            window.change_property(
                self.dpy.get_atom('_NET_SUPPORTING_WM_CHECK'),
                Xatom.WINDOW,
                32,
                [self.support_window.id],
            )
        self.support_window.change_property(
            self.dpy.get_atom('_NET_WM_NAME'),
            Xatom.STRING,
            8,
            self.WM_NAME,
        )

    def loop(self):
        """Start the X event loop."""
        log.info("event loop started")
        while 1:
            ev = self.root.display.next_event()
            log.debug("Got event {}".format(ev))
            handler = self._handlers.get(ev.type)
            if handler:
                handler(ev)

            self._update_clients()

    def activate(self, window):
        """Activate the given window, raise it and focus it."""
        log.debug("activating window {}".format(window))
        window.raise_window()
        window.set_input_focus(revert_to=X.RevertToNone, time=X.CurrentTime)
        self.root.change_property(
            self.dpy.get_atom('_NET_ACTIVE_WINDOW'),
            Xatom.WINDOW,
            32,
            [window.id] if window else [X.NONE],
        )
        # re-order window_stack so that the active window is at
        # window_stack[-1]
        try:
            index = self.window_stack.index(window)
        except ValueError:
            # Okay, fine then
            pass
        else:
            self.window_stack = (self.window_stack[index + 1:] +
                                 self.window_stack[:index + 1])

    def _update_clients(self):
        """Update _NET_CLIENT_LIST and _NET_ACTIVE_WINDOW attributes."""
        self.root.change_property(
            self.dpy.get_atom('_NET_CLIENT_LIST'),
            Xatom.WINDOW,
            32,
            [window.id for window in self.windows],
        )
        self.root.change_property(
            self.dpy.get_atom('_NET_ACTIVE_WINDOW'),
            Xatom.WINDOW,
            32,
            [self.window_stack[-1].id] if self.window_stack else [X.NONE],
        )

    def on_MapNotify(self, ev):
        """Called when a window is shown on screen ("mapped")."""
        width, height = self.dimensions
        ev.window.configure(x=0, y=0, width=width, height=height)
        log.debug("window created: {}".format(ev.window))
        self.windows.append(ev.window)
        self.window_stack.append(ev.window)
        self.activate(ev.window)

    def on_UnmapNotify(self, ev):
        """Called when a window is unmapped from the screen."""
        log.debug("window destroyed: {}".format(ev.window))
        try:
            self.windows.remove(ev.window)
            self.window_stack.remove(ev.window)
        except ValueError:
            log.debug("window was not in self.windows!")
        if self.window_stack:
            self.activate(self.window_stack[-1])

    def on_KeyPress(self, ev):
        """Called when a key that we're listening for is pressed."""
        # We only grabbed one key combination, so we don't need to check which
        # keys were actually pressed.
        if ev.child == X.NONE:
            return
        log.debug("cycling through available windows")
        if self.window_stack:
            self.activate(self.window_stack[0])

    def on_ClientMessage(self, ev):
        """Called when a ClientMessage is received."""
        if ev.client_type == self.ATOM_ACTIVE_WINDOW:
            log.info("external request to activate {}".format(ev.window))
            self.activate(ev.window)


def repl():
    import code
    code.interact(local=globals())


def main():
    if '--help' in sys.argv:
        print(__doc__)
        return

    if '--debug' in sys.argv:
        log.setLevel(logging.DEBUG)

    if '--repl' in sys.argv:
        import threading
        threading.Thread(target=repl).start()

    global wm
    wm = QuteWM()
    wm.loop()


if __name__ == '__main__':
    main()
