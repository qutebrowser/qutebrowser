# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Jay Kamat <jaygkamat@gmail.com>
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

"""A simple throttling decorator."""

import typing
import time
import functools

from PyQt5.QtCore import QObject

from qutebrowser.utils import usertypes


class throttle:  # noqa: N801,N806 pylint: disable=invalid-name

    """A simple function decorator to throttle calls.

    If a request comes in, it will be processed immediately. If another request
    comes in too soon, it is ignored, but will be processed when a timeout
    ends. If another request comes in, it will update the pending request.

    """

    def __init__(self, delay_ms: int) -> None:
        """Save arguments for throttle decorator.

        Args:
            delay_ms: The time to wait before allowing another call of the
                         function. -1 disables the wrapper.
        """
        self._delay_ms = delay_ms
        # None if no call is pending, a tuple of (args, kwargs) (to call with)
        # if a call is pending.
        self._pending_call = (None) \
            #type:typing.Optional[typing.Tuple[typing.Sequence,typing.Mapping]]
        self._last_call_ms = None  # type: typing.Optional[int]
        self._timer = usertypes.Timer(None, 'throttle-timer')
        self._timer.setSingleShot(True)

    def __call__(self, func: typing.Callable) -> typing.Callable:
        @functools.wraps(func)
        def wrapped_fn(*args, **kwargs):
            cur_time_ms = int(time.monotonic() * 1000)
            if self._pending_call is None:
                if (self._last_call_ms is None or
                        cur_time_ms - self._last_call_ms > self._delay_ms):
                    # Call right now
                    self._last_call_ms = cur_time_ms
                    func(*args, **kwargs)
                    return

                # Start a pending call
                def call_pending():
                    func(*self._pending_call[0], **self._pending_call[1])
                    self._pending_call = None
                    self._last_call_ms = int(time.monotonic() * 1000)

                self._timer.setInterval(self._delay_ms -
                                        (cur_time_ms - self._last_call_ms))
                # Disconnect any existing calls, continue if no connections.
                try:
                    self._timer.timeout.disconnect()
                except TypeError:
                    pass
                self._timer.timeout.connect(call_pending)
                self._timer.start()
            # Update arguments for an existing pending call
            self._pending_call = (args, kwargs)
        wrapped_fn.throttle = self  # type: ignore
        return wrapped_fn

    def set_delay(self, delay_ms: int) -> None:
        """Set the delay to wait between invocation of this function."""
        self._delay_ms = delay_ms

    def cancel(self) -> None:
        """Cancel any pending instance of this timer."""
        self._timer.stop()

    def set_parent(self, parent: QObject) -> None:
        """Set the parent for the throttle's QTimer.

        Calling this is strongly recommended if throttle is used inside a
        QObject. This ensures that the underlying method doesn't get called
        after the C++ object was deleted.
        """
        self._timer.setParent(parent)
