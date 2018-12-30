# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Jay Kamat <jaygkamat@gmail.com>
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

from PyQt5.QtCore import QTimer


class throttle:  # noqa: N801,N806 pylint: disable=invalid-name

    """A simple function decorator to throttle calls.

    If a request comes in, it will be processed immediately. If another request
    comes in too soon, it is ignored, but will be processed when a timeout
    ends. If another request comes in, it will update the pending request.

    """

    def __init__(self, throttle_ms: int) -> None:
        """Save arguments for throttle decorator.

        Args:
            throttle_ms: The time to wait before allowing another call of the
                         function. -1 disables the wrapper.
        """
        self.throttle_ms = throttle_ms
        # False if no call is pending, a tuple of (args, kwargs) (to call with)
        # if a call is pending.
        self._pending_call = False
        self._last_call_ms = None

    def __call__(self, func: typing.Callable) -> typing.Callable:
        @functools.wraps(func)
        def wrapped_fn(*args, **kwargs):
            cur_time_ms = int(time.monotonic() * 1000)
            if self._pending_call is False:
                if (self._last_call_ms is None or
                        cur_time_ms - self._last_call_ms > self.throttle_ms):
                    # Call right now
                    self._last_call_ms = cur_time_ms
                    func(*args, **kwargs)
                    return

                # Start a pending call
                def call_pending():
                    func(*self._pending_call[0], **self._pending_call[1])
                    self._pending_call = False
                    self._last_call_ms = int(time.monotonic() * 1000)

                QTimer.singleShot(
                    self.throttle_ms - (cur_time_ms - self._last_call_ms),
                    call_pending)
            # Update arguments for an existing pending call
            self._pending_call = (args, kwargs)
        wrapped_fn.throttle_set = self.throttle_set  # type: ignore
        return wrapped_fn

    def throttle_set(self, throttle_val: int) -> None:
        self.throttle_ms = throttle_val
