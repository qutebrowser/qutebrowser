# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Loader for qutebrowser extensions."""

import pkgutil
import types
import sys
import pathlib
import importlib
import argparse
import dataclasses
from typing import Callable, Iterator, List, Optional, Set, Tuple

from PyQt5.QtCore import pyqtSlot

from qutebrowser import components
from qutebrowser.config import config
from qutebrowser.utils import log, standarddir
from qutebrowser.misc import objects


# ModuleInfo objects for all loaded plugins
_module_infos = []


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
    init_hook: Optional[Callable] = None
    config_changed_hooks: List[Tuple[Optional[str], Callable]] = dataclasses.field(
        default_factory=list)


@dataclasses.dataclass
class ExtensionInfo:

    """Information about a qutebrowser extension."""

    name: str


def add_module_info(module: types.ModuleType) -> ModuleInfo:
    """Add ModuleInfo to a module (if not added yet)."""
    # pylint: disable=protected-access
    if not hasattr(module, '__qute_module_info'):
        module.__qute_module_info = ModuleInfo()  # type: ignore[attr-defined]
    return module.__qute_module_info  # type: ignore[attr-defined]


def load_components(*, skip_hooks: bool = False) -> None:
    """Load everything from qutebrowser.components."""
    for info in walk_components():
        _load_component(info, skip_hooks=skip_hooks)


def walk_components() -> Iterator[ExtensionInfo]:
    """Yield ExtensionInfo objects for all modules."""
    if hasattr(sys, 'frozen'):
        yield from _walk_pyinstaller()
    else:
        yield from _walk_normal()


def _on_walk_error(name: str) -> None:
    raise ImportError("Failed to import {}".format(name))


def _walk_normal() -> Iterator[ExtensionInfo]:
    """Walk extensions when not using PyInstaller."""
    for _finder, name, ispkg in pkgutil.walk_packages(
            # Only packages have a __path__ attribute,
            # but we're sure this is one.
            path=components.__path__,  # type: ignore[attr-defined]
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


def _walk_pyinstaller() -> Iterator[ExtensionInfo]:
    """Walk extensions when using PyInstaller.

    See https://github.com/pyinstaller/pyinstaller/issues/1905

    Inspired by:
    https://github.com/webcomics/dosage/blob/master/dosagelib/loader.py
    """
    toc: Set[str] = set()
    for importer in pkgutil.iter_importers('qutebrowser'):
        if hasattr(importer, 'toc'):
            toc |= importer.toc  # type: ignore[union-attr]
    for name in toc:
        if name.startswith(components.__name__ + '.'):
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
