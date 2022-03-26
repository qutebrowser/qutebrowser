# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Implementation of the command debug-cache-stats.

Because many modules depend on this command, this needs to have as few
dependencies as possible to avoid cyclic dependencies.
"""

import weakref
import sys
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from qutebrowser.utils import log


# The second element of each tuple should be a lru_cache wrapped function
_CACHE_FUNCTIONS: List[Tuple[str, Any]] = []


_T = TypeVar('_T', bound=Callable[..., Any])


def register(name: Optional[str] = None) -> Callable[[_T], _T]:
    """Register a lru_cache wrapped function for debug_cache_stats."""
    def wrapper(fn: _T) -> _T:
        fn_name = fn.__name__ if name is None else name
        if sys.version_info < (3, 9):
            log.misc.vdebug(  # type: ignore[attr-defined]
                'debugcachestats not supported on python < 3.9, not adding \'%s\'',
                fn_name,
            )
            return fn

        else:
            fn_ref = weakref.ref(fn)
            _CACHE_FUNCTIONS.append((fn_name, fn_ref))
            return fn
    return wrapper


def debug_cache_stats() -> None:
    """Print LRU cache stats."""
    for idx, (name, fn_ref) in reversed(list(enumerate(_CACHE_FUNCTIONS))):
        fn = fn_ref()
        if not fn:
            _CACHE_FUNCTIONS.pop(idx)
            continue
        log.misc.info('{}: {}'.format(name, fn.cache_info()))
