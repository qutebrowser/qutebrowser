# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Loader for qutebrowser extensions."""

import pkgutil
import types
import pathlib
import importlib
import argparse
import dataclasses
from typing import Callable, Iterator, List, Optional, Tuple

from qutebrowser.qt.core import pyqtSlot

from qutebrowser import components
from qutebrowser.config import config
from qutebrowser.utils import log, standarddir
from qutebrowser.misc import objects


# ModuleInfo objects for all loaded plugins
_module_infos: List["ModuleInfo"] = []

InitHookType = Callable[['InitContext'], None]
ConfigChangedHookType = Callable[[], None]


@dataclasses.dataclass
class InitContext:

    """Context an extension gets in its init hook."""

    data_dir: pathlib.Path
    config_dir: pathlib.Path
    args: argparse.Namespace


@dataclasses.dataclass
class ModuleInfo:

    """Information attached to an extension module.

    This gets used by qutebrowser.api.hook.
    """

    skip_hooks: bool = False
    init_hook: Optional[InitHookType] = None
    config_changed_hooks: List[
        Tuple[
            Optional[str],
            ConfigChangedHookType,
        ]
    ] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ExtensionInfo:

    """Information about a qutebrowser extension."""

    name: str


def add_module_info(module: types.ModuleType) -> ModuleInfo:
    """Add ModuleInfo to a module (if not added yet)."""
    # pylint: disable=protected-access
    if not hasattr(module, '__qute_module_info'):
        module.__qute_module_info = ModuleInfo()  # type: ignore[attr-defined]
    return module.__qute_module_info


def load_components(*, skip_hooks: bool = False) -> None:
    """Load everything from qutebrowser.components."""
    for info in walk_components():
        _load_component(info, skip_hooks=skip_hooks)


def walk_components() -> Iterator[ExtensionInfo]:
    """Yield ExtensionInfo objects for all modules."""
    for _finder, name, ispkg in pkgutil.walk_packages(
            path=components.__path__,
            prefix=components.__name__ + '.',
            onerror=_on_walk_error):
        if ispkg:
            continue
        if name == 'qutebrowser.components.adblock':
            # WORKAROUND for packaging issues where the old adblock.py file is still
            # lingering around.
            log.extensions.debug("Ignoring stale 'adblock' component")
            continue
        yield ExtensionInfo(name=name)


def _get_init_context() -> InitContext:
    """Get an InitContext object."""
    return InitContext(data_dir=pathlib.Path(standarddir.data()),
                       config_dir=pathlib.Path(standarddir.config()),
                       args=objects.args)


def _load_component(info: ExtensionInfo, *,
                    skip_hooks: bool = False) -> types.ModuleType:
    """Load the given extension and run its init hook (if any).

    Args:
        skip_hooks: Whether to skip all hooks for this module.
                    This is used to only run @cmdutils.register decorators.
    """
    log.extensions.debug("Importing {}".format(info.name))
    mod = importlib.import_module(info.name)

    mod_info = add_module_info(mod)
    if skip_hooks:
        mod_info.skip_hooks = True

    if mod_info.init_hook is not None and not skip_hooks:
        log.extensions.debug("Running init hook {!r}"
                             .format(mod_info.init_hook.__name__))
        mod_info.init_hook(_get_init_context())

    _module_infos.append(mod_info)

    return mod


@pyqtSlot(str)
def _on_config_changed(changed_name: str) -> None:
    """Call config_changed hooks if the config changed."""
    for mod_info in _module_infos:
        if mod_info.skip_hooks:
            continue
        for option, hook in mod_info.config_changed_hooks:
            if option is None:
                hook()
            else:
                cfilter = config.change_filter(option)
                cfilter.validate()
                if cfilter.check_match(changed_name):
                    hook()


def init() -> None:
    config.instance.changed.connect(_on_config_changed)


def _on_walk_error(name: str) -> None:
    raise ImportError("Failed to import {}".format(name))
