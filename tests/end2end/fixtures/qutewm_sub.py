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

Exit codes:
    42 - another window manager is running
"""

import sys
import signal
import logging

from Xlib.display import Display
from Xlib import X, XK, Xatom, Xutil

LOG_FORMAT = ('{asctime:8} {levelname:8} {name:10}'
              ' {module}:{funcName}:{lineno} {message}')
logging.basicConfig(
    style='{',
    format=LOG_FORMAT,
    level=logging.INFO,
)
log = logging.getLogger('qutewm')


class AtomBag:

    """A class which has important X atoms as attributes.

    The atoms are fetched and cached in the initializer.

    Attributes:
        active_window: _NET_ACTIVE_WINDOW
        wm_state: _NET_WM_STATE
        demands_attention: _NET_WM_STATE_DEMANDS_ATTENTION
        supported: _NET_SUPPORTED
        client_list: _NET_CLIENT_LIST
        supporting_wm: _NET_SUPPORTING_WM_CHECK
        wm_hints: WM_HINTS
    """

    def __init__(self, dpy):
        atom = dpy.get_atom
        self.active_window = atom('_NET_ACTIVE_WINDOW')
        self.wm_state = atom('_NET_WM_STATE')
        self.demands_attention = atom('_NET_WM_STATE_DEMANDS_ATTENTION')
        self.supported = atom('_NET_SUPPORTED')
        self.client_list = atom('_NET_CLIENT_LIST')
        self.supporting_wm = atom('_NET_SUPPORTING_WM_CHECK')
        # there's also WM_NAME, so prefix with net_ to distinguish
        self.net_wm_name = atom('_NET_WM_NAME')
        self.wm_hints = Xatom.WM_HINTS


class Quit(Exception):

    """Exception to quit qutewm."""


class QuteWM:

    """Main class for the qutewm window manager.

    Attributes:
        dpy: The Display.
        dimensions: The screen's dimensions (width, height).
        _retcode: Exit code of the window manager.
        _needs_update: True if the client list or the active window property
                       needs to be updated.
        windows: A list of all managed windows in mapping order.
        window_stack: A list of all windows in stack order.
        root: The root window.
        support_window: The window for the _NET_SUPPORTING_WM_CHECK.
        atoms: AtomBag for the window manager.
    """

    WM_NAME = b'qutewm'

    ROOT_EVENT_MASK = X.SubstructureNotifyMask | X.SubstructureRedirectMask
    CLIENT_EVENT_MASK = (X.StructureNotifyMask | X.PropertyChangeMask |
                         X.FocusChangeMask)

    STATE_REMOVE = 0
    STATE_ADD = 1
    STATE_TOGGLE = 2

    def __init__(self):
        log.debug("initializing")
        self._handlers = {
            X.MapNotify: self._on_map_notify,
            X.UnmapNotify: self._on_unmap_notify,
            X.ClientMessage: self._on_client_message,
            X.MapRequest: self._on_map_request,
            X.ConfigureRequest: self._on_configure_request,
            X.CirculateRequest: self._on_circulate_request,
            X.PropertyNotify: self._on_property_notify,
            X.FocusIn: self._on_focus_in,
        }
        self.dpy = Display()
        self.dpy.set_error_handler(self._error_handler)

        screen_width = self.dpy.screen().width_in_pixels
        screen_height = self.dpy.screen().height_in_pixels
        self.dimensions = (screen_width, screen_height)

        self._retcode = None
        self._needs_update = False
        self.root = self.dpy.screen().root
        self.support_window = None
        self.windows = []
        self.window_stack = []

        self.root.change_attributes(event_mask=self.ROOT_EVENT_MASK,
                                    onerror=self._wm_running)

        self.atoms = AtomBag(self.dpy)

        self._set_supported_attribute()
        self._set_supporting_wm_check()

    def _wm_running(self, error, request):
        """Called when another WM is already running."""
        log.error("Another window manager is running, exiting")
        # This is called async, which means we can't just raise an exception,
        # we need to signal the main thread to stop.
        self._retcode = 42

    def _error_handler(self, error, request):
        # This is called async, which means we can't just raise an exception,
        # we need to signal the main thread to stop.
        if self._retcode is None:
            log.error(error)

    def _set_supported_attribute(self):
        """Set the _NET_SUPPORTED attribute on the root window."""
        attributes = [
            self.atoms.supported,
            self.atoms.active_window,
            self.atoms.client_list,
            self.atoms.wm_state,
        ]
        self.root.change_property(
            self.atoms.supported,
            Xatom.ATOM,
            32,
            attributes,
        )

    def _set_supporting_wm_check(self):
        """Create and set a window for _NET_SUPPORTING_WM_CHECK."""
        self.support_window = self.root.create_window(
            0, 0, 10, 10, 0, self.dpy.screen().root_depth)

        for window in [self.root, self.support_window]:
            window.change_property(
                self.atoms.supporting_wm,
                Xatom.WINDOW,
                32,
                [self.support_window.id],
            )
        self.support_window.change_property(
            self.atoms.net_wm_name,
            Xatom.STRING,
            8,
            self.WM_NAME,
        )

    def loop(self):
        """Start the X event loop.

        Return:
            The manager's exit code.
        """
        if self._retcode is not None:
            # avoid the "event loop started" message if we exit anyway
            return self._retcode
        log.info("event loop started")
        while 1:
            if self._retcode is not None:
                return self._retcode
            try:
                ev = self.root.display.next_event()
                handler = self._handlers.get(ev.type)
                if handler:
                    handler(ev)
            except Quit:
                return self._retcode
            #log.debug("Got event {}".format(ev))
            self._update_clients()

    def quit(self, reason=None):
        """Quit the window manager."""
        self._retcode = 0
        reason_str = ''
        if reason is not None:
            reason_str = ' ({})'.format(reason)
        log.info("quitting qutewm" + reason_str)
        self.support_window.destroy()
        # don't wait for another event...
        raise Quit

    def activate(self, window):
        """Activate the given window, raise it and focus it."""
        window.raise_window()
        window.set_input_focus(revert_to=X.RevertToNone, time=X.CurrentTime)

    def _update_clients(self):
        """Update _NET_CLIENT_LIST and _NET_ACTIVE_WINDOW attributes."""
        if not self._needs_update:
            return

        self.root.change_property(
            self.atoms.client_list,
            Xatom.WINDOW,
            32,
            [window.id for window in self.windows],
        )
        self.root.change_property(
            self.atoms.active_window,
            Xatom.WINDOW,
            32,
            [self.window_stack[-1].id] if self.window_stack else [X.NONE],
        )
        self._needs_update = False

    def _on_map_notify(self, ev):
        """Called when a window is shown on screen ("mapped")."""
        width, height = self.dimensions
        ev.window.configure(x=0, y=0, width=width, height=height)
        log.info("window created: [{:#x}]".format(ev.window.id))
        self._manage_window(ev.window)

    def _on_map_request(self, ev):
        """Called when a MapRequest is intercepted."""
        ev.window.map()

    def _on_configure_request(self, ev):
        """Called when a ConfigureRequest is intercepted."""
        ev.window.configure(x=ev.x, y=ev.y, width=ev.width, height=ev.height,
                            border_width=ev.border_width,
                            value_mask=ev.value_mask)

    def _on_circulate_request(self, ev):
        """Called when a CirculateRequest is intercepted."""
        ev.window.circulate(ev.place)

    def _on_unmap_notify(self, ev):
        """Called when a window is unmapped from the screen."""
        log.debug("window unmapped: {}".format(ev.window))
        if ev.event == self.root and not ev.from_configure:
            log.debug("ignoring synthetic event")
            return
        log.info("window closed: [{:#x}]".format(ev.window.id))
        self._unmanage_window(ev.window)
        if self.window_stack:
            self.activate(self.window_stack[-1])

    def _on_client_message(self, ev):
        """Called when a ClientMessage is received."""
        if ev.client_type == self.atoms.active_window:
            log.debug("external request to activate {}".format(ev.window))
            if ev.window in self.windows:
                self.activate(ev.window)
            else:
                log.debug("window to activate is not managed!")
        elif ev.client_type == self.atoms.wm_state:
            self._handle_wm_state(ev)

    def _on_property_notify(self, ev):
        """Called when a PropertyNotify event is received."""
        if ev.atom == self.atoms.wm_hints:
            hints = ev.window.get_wm_hints()
            if hints is None:
                return
            if hints.flags & Xutil.UrgencyHint:
                log.debug("urgency switch to {} (via WM_HINTS)"
                          .format(ev.window))
                self.activate(ev.window)

    def _on_focus_in(self, ev):
        """Called when a FocusIn event is received."""
        window = ev.window
        self.root.change_property(
            self.atoms.active_window,
            Xatom.WINDOW,
            32,
            [window.id] if window else [X.NONE],
        )
        self._needs_update = True
        self._update_clients()
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
        log.info("window activated: [{:#x}]".format(window.id))

    def _handle_wm_state(self, ev):
        """Handle the _NET_WM_STATE client message."""
        client_properties = ev.window.get_property(self.atoms.wm_state,
                                                   Xatom.ATOM, 0, 32)
        if client_properties is None:
            client_properties = set()
        else:
            client_properties = set(client_properties.value)

        action = ev.data[1][0]
        updates = {ev.data[1][1]}
        if ev.data[1][2] != 0:
            updates.add(ev.data[1][2])

        if action == self.STATE_ADD:
            client_properties.update(updates)
        elif action == self.STATE_REMOVE:
            client_properties.difference_update(updates)
        elif action == self.STATE_TOGGLE:
            for atom in updates:
                if atom in client_properties:
                    client_properties.remove(atom)
                else:
                    client_properties.add(atom)
        else:
            log.error("unknown action: {}".format(action))

        log.debug("client properties for {}: {}".format(ev.window,
                                                        client_properties))
        ev.window.change_property(self.atoms.wm_state, Xatom.ATOM, 32,
                                  client_properties)

        if self.atoms.demands_attention in client_properties:
            log.debug("urgency switch to {} (via _NET_WM_STATE)"
                      .format(ev.window))
            self.activate(ev.window)

    def _manage_window(self, window):
        """Add the given window to the list of managed windows."""
        window.change_attributes(event_mask=self.CLIENT_EVENT_MASK)
        self.windows.append(window)
        self.window_stack.append(window)
        self._needs_update = True
        self.activate(window)

    def _unmanage_window(self, window):
        """Remove the given window from the list of managed windows."""
        try:
            self.windows.remove(window)
            self.window_stack.remove(window)
        except ValueError:
            log.debug("window was not in self.windows!")
        else:
            self._needs_update = True


def main():
    if '--help' in sys.argv:
        print(__doc__)
        return

    if '--debug' in sys.argv:
        log.setLevel(logging.DEBUG)

    wm = QuteWM()
    signal.signal(signal.SIGTERM, lambda signum, frame: wm.quit('SIGTERM'))
    signal.signal(signal.SIGINT, lambda signum, frame: wm.quit('Ctrl-C'))
    sys.exit(wm.loop())


if __name__ == '__main__':
    main()
