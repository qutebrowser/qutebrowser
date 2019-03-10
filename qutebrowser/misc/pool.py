# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Jay Kamat <jaygkamat@gmail.com>
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


"""Implementation of a basic object pool."""

import typing
import collections


# The type we will store in the pool
StoredType = typing.TypeVar('StoredType')


class Pool(typing.Generic[StoredType]):

    """A object pool data structure.

    Sometimes, the cost of initializing objects is high, but we need a dynamic
    amount of objects. A Pool helps manage these objects.
    """

    MAX_SIZE_WINDOW = 20

    def __init__(self,
                 obj_constructor: typing.Callable[..., StoredType],
                 min_size: int,
                 cleanup_fn: typing.Optional[
                     typing.Callable[[StoredType], None]] = None) -> None:
        self._constructor = obj_constructor
        self._cleanup_fn = cleanup_fn
        self._min_size = min_size
        self._pool = []  # type: typing.List[StoredType]
        self._active_objects = 0
        self._active_objects_peak = 0
        self._max_size_queue = collections.deque([], Pool.MAX_SIZE_WINDOW) \
            # type: typing.Deque[int]

    def acquire(self, *args, initialize_fn: typing.Optional[
            typing.Callable[[StoredType], None]] = None) -> StoredType:
        """Get an object from this pool.

        If one does not exist, it will be constructed on the fly.

        Pass any arguments that you would pass to the constructor to this
        function. These arguments may not be used, if an object is pulled from
        the pool.

        Use initialize_fn to finalize any objects being re-used from the pool.
        initialize_fn is not called if constructing a new object.

        When done, you should use release to return the object.

        """
        self._active_objects += 1
        self._active_objects_peak = max(self._active_objects,
                                        self._active_objects_peak)
        try:
            elt = self._pool.pop()
            if initialize_fn:
                initialize_fn(elt)
            return elt
        except IndexError:
            return self._constructor(*args)

    def release(self, to_free: StoredType) -> None:
        """Free a given object.

        This object may be placed back into the pool.

        When passing to release, you should drop your reference on the object
        (treat it as a free pointer).

        If a cleanup function was defined, it is called on the object.

        """
        self._active_objects = max(self._active_objects - 1, 0)
        if self._cleanup_fn:
            self._cleanup_fn(to_free)
        self._pool.append(to_free)

        if self._active_objects == 0:
            self._housekeeping()

    def _housekeeping(self) -> None:
        """Run housekeeping on this pool.

        Not strictly needed, but in order to ensure the pool is not overflowing
        or underflowing, housekeeping should run whenever the pool is 'full'.

        """
        if self._active_objects_peak == 0:
            # Nothing happened, abort
            return

        self._max_size_queue.append(self._active_objects_peak)
        self._active_objects_peak = 0
        del self._pool[max(self._min_size, max(self._max_size_queue)):]
