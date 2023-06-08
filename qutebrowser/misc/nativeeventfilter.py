# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2023 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Native Qt event filter.

This entire file is a giant WORKAROUND for https://bugreports.qt.io/browse/QTBUG-114334.
"""

import ctypes

from qutebrowser.qt.core import QAbstractNativeEventFilter

from qutebrowser.misc import objects


# Needs to be saved to avoid garbage collection
_instance = None


class xcb_ge_generic_event_t(ctypes.Structure):
    """See https://xcb.freedesktop.org/manual/structxcb__ge__generic__event__t.html.

    Also used for xcb_generic_event_t as the structures overlap:
    https://xcb.freedesktop.org/manual/structxcb__generic__event__t.html
    """
    _fields_ = [
        ("response_type", ctypes.c_uint8),
        ("extension", ctypes.c_uint8),
        ("sequence", ctypes.c_uint16),
        ("length", ctypes.c_uint32),
        ("event_type", ctypes.c_uint16),
        ("pad0", ctypes.c_uint8 * 22),
        ("full_sequence", ctypes.c_uint32),
    ]


_XCB_GE_GENERIC = 35
_PROBLEMATIC_XINPUT_EVENTS = [
    27,  # XCB_INPUT_GESTURE_PINCH_BEGIN
    28,  # XCB_INPUT_GESTURE_PINCH_UPDATE
    29,  # XCB_INPUT_GESTURE_PINCH_END
    30,  # XCB_INPUT_GESTURE_SWIPE_BEGIN
    31,  # XCB_INPUT_GESTURE_SWIPE_UPDATE
    32,  # XCB_INPUT_GESTURE_SWIPE_END
]

class xcb_query_extension_reply_t(ctypes.Structure):
    """https://xcb.freedesktop.org/manual/structxcb__query__extension__reply__t.html."""
    _fields_ = [
        ('response_type', ctypes.c_uint8),
        ('pad0', ctypes.c_uint8),
        ('sequence', ctypes.c_uint16),
        ('length', ctypes.c_uint32),
        ('present', ctypes.c_uint8),
        ('major_opcode', ctypes.c_uint8),
        ('first_event', ctypes.c_uint8),
        ('first_error', ctypes.c_uint8),
    ]


class NativeEventFilter(QAbstractNativeEventFilter):

    def __init__(self) -> None:
        super().__init__()
        xcb = ctypes.cdll.LoadLibrary('libxcb.so.1')
        xcb.xcb_connect.restype = ctypes.POINTER(ctypes.c_void_p)
        xcb.xcb_query_extension_reply.restype = ctypes.POINTER(xcb_query_extension_reply_t)

        conn = xcb.xcb_connect(None, None)
        assert conn
        assert not xcb.xcb_connection_has_error(conn)

        # Get major opcode ID of Xinput extension
        name = b'XInputExtension'
        cookie = xcb.xcb_query_extension(conn, len(name), name)
        reply = xcb.xcb_query_extension_reply(conn, cookie, None)
        assert reply

        if not reply.contents.present:
            self.xinput_opcode = None
        else:
            self.xinput_opcode = reply.contents.major_opcode

        xcb.xcb_disconnect(conn)

    def nativeEventFilter(self, evtype: bytes, message: int) -> Tuple[bool, int]:
        # We're only installed when the platform plugin is xcb
        assert evtype == b'xcb_generic_event_t', evtype

        # We cast to xcb_ge_generic_event_t, which overlaps with xcb_generic_event_t.
        # .extension and .event_type will only make sense if this is an
        # XCB_GE_GENERIC event, but this is the first thing we check in the 'if'
        # below anyways.
        event = ctypes.cast(int(message), ctypes.POINTER(xcb_ge_generic_event_t)).contents

        if (
            event.response_type == _XCB_GE_GENERIC and
            event.extension == self.xinput_opcode and
            event.event_type in _PROBLEMATIC_XINPUT_EVENTS
        ):
            print("Ignoring problematic XInput event", event.event_type)
            return (True, 0)

        return (False, 0)


def init() -> None:
    global _instance
    _instance = NativeEventFilter()
    objects.qapp.installNativeEventFilter(_instance)
