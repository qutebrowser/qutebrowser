# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Implementation of the command debug-cache-stats.

Because many modules depend on this command, this needs to have as few
dependencies as possible to avoid cyclic dependencies.
"""

import typing


# The second element of each tuple should be a lru_cache wrapped function
_CACHE_FUNCTIONS = []  # type: typing.List[typing.Tuple[str, typing.Any]]


_T = typing.TypeVar('_T', bound=typing.Callable)


def register(name: typing.Optional[str] = None) -> typing.Callable[[_T], _T]:
    """Register a lru_cache wrapped function for debug_cache_stats."""
    def wrapper(fn: _T) -> _T:
        _CACHE_FUNCTIONS.append((fn.__name__ if name is None else name, fn))
        return fn
    return wrapper


def debug_cache_stats() -> None:
    """Print LRU cache stats."""
    from qutebrowser.utils import log
    for name, fn in _CACHE_FUNCTIONS:
        log.misc.info('{}: {}'.format(name, fn.cache_info()))
