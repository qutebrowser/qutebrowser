# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Jay Kamat <jaygkamat@gmail.com>
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

"""A throttle for throttling function calls."""

import typing
import time

import attr
from PyQt5.QtCore import QObject

from qutebrowser.utils import usertypes


@attr.s
class _CallArgs:

    args = attr.ib()  # type: typing.Sequence[typing.Any]
    kwargs = attr.ib()  # type: typing.Mapping[str, typing.Any]


class Throttle(QObject):

    """A throttle to throttle calls.

    If a request comes in, it will be processed immediately. If another request
    comes in too soon, it is ignored, but will be processed when a timeout
    ends. If another request comes in, it will update the pending request.
    """

    def __init__(self,
                 func: typing.Callable,
                 delay_ms: int,
                 parent: QObject = None) -> None:
        """Constructor.

        Args:
            delay_ms: The time to wait before allowing another call of the
                         function. -1 disables the wrapper.
            func: The function/method to call on __call__.
            parent: The parent object.
        """
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._func = func
        self._pending_call = None  # type: typing.Optional[_CallArgs]
        self._last_call_ms = None  # type: typing.Optional[int]
        self._timer = usertypes.Timer(self, 'throttle-timer')
        self._timer.setSingleShot(True)

    def _call_pending(self) -> None:
        """Start a pending call."""
        assert self._pending_call is not None
        self._func(*self._pending_call.args, **self._pending_call.kwargs)
        self._pending_call = None
        self._last_call_ms = int(time.monotonic() * 1000)

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        cur_time_ms = int(time.monotonic() * 1000)
        if self._pending_call is None:
            if (self._last_call_ms is None or
                    cur_time_ms - self._last_call_ms > self._delay_ms):
                # Call right now
                self._last_call_ms = cur_time_ms
                self._func(*args, **kwargs)
                return

            self._timer.setInterval(self._delay_ms -
                                    (cur_time_ms - self._last_call_ms))
            # Disconnect any existing calls, continue if no connections.
            try:
                self._timer.timeout.disconnect()
            except TypeError:
                pass
            self._timer.timeout.connect(self._call_pending)
            self._timer.start()

        # Update arguments for an existing pending call
        self._pending_call = _CallArgs(args=args, kwargs=kwargs)

    def set_delay(self, delay_ms: int) -> None:
        """Set the delay to wait between invocation of this function."""
        self._delay_ms = delay_ms

    def cancel(self) -> None:
        """Cancel any pending instance of this timer."""
        self._timer.stop()
