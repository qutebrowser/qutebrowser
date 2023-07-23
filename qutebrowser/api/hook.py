# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=invalid-name

"""Hooks for extensions."""

import importlib
from typing import Callable, Any


from qutebrowser.extensions import loader


def _add_module_info(func: Callable[..., Any]) -> loader.ModuleInfo:
    """Add module info to the given function."""
    module = importlib.import_module(func.__module__)
    return loader.add_module_info(module)


class init:

    """Decorator to mark a function to run when initializing.

    The decorated function gets called with a
    :class:`qutebrowser.api.apitypes.InitContext` as argument.

    Example::

        @hook.init()
        def init(_context):
            message.info("Extension initialized.")
    """

    def __call__(self, func: loader.InitHookType) -> loader.InitHookType:
        info = _add_module_info(func)
        if info.init_hook is not None:
            raise ValueError("init hook is already registered!")
        info.init_hook = func
        return func


class config_changed:

    """Decorator to get notified about changed configs.

    By default, the decorated function is called when any change in the config
    occurs::

        @hook.config_changed()
        def on_config_changed():
            ...

    When an option name is passed, it's only called when the given option was
    changed::

        @hook.config_changed('content.javascript.enabled')
        def on_config_changed():
            ...

    Alternatively, a part of an option name can be specified. In the following
    snippet, ``on_config_changed`` gets called when either
    ``bindings.commands`` or ``bindings.key_mappings`` have changed::

        @hook.config_changed('bindings')
        def on_config_changed():
            ...
    """

    def __init__(self, option_filter: str = None) -> None:
        self._filter = option_filter

    def __call__(
        self,
        func: loader.ConfigChangedHookType,
    ) -> loader.ConfigChangedHookType:
        info = _add_module_info(func)
        info.config_changed_hooks.append((self._filter, func))
        return func
