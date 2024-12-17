# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Implementation of the command debug-cache-stats.

Because many modules depend on this command, this needs to have as few
dependencies as possible to avoid cyclic dependencies.
"""

import weakref
from typing import Any, Optional, TypeVar
from collections.abc import MutableMapping, Callable

from qutebrowser.utils import log


# The callable should be a lru_cache wrapped function
_CACHE_FUNCTIONS: MutableMapping[str, Any] = weakref.WeakValueDictionary()


_T = TypeVar('_T', bound=Callable[..., Any])


def register(name: Optional[str] = None) -> Callable[[_T], _T]:
    """Register a lru_cache wrapped function for debug_cache_stats."""
    def wrapper(fn: _T) -> _T:
        fn_name = fn.__name__ if name is None else name
        _CACHE_FUNCTIONS[fn_name] = fn
        return fn
    return wrapper


def debug_cache_stats() -> None:
    """Print LRU cache stats."""
    for name, fn in _CACHE_FUNCTIONS.items():
        log.misc.info('{}: {}'.format(name, fn.cache_info()))
