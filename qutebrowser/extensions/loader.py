# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Loader for qutebrowser extensions."""

import importlib.abc
import pkgutil
import types
import typing
import sys

import attr

from qutebrowser import components
from qutebrowser.utils import log


@attr.s
class InitContext:

    """Context an extension gets in its init hook."""


@attr.s
class ModuleInfo:

    """Information attached to an extension module.

    This gets used by qutebrowser.api.hook.
    """

    init_hook = attr.ib(None)  # type: typing.Optional[typing.Callable]


@attr.s
class ExtensionInfo:

    """Information about a qutebrowser extension."""

    name = attr.ib()  # type: str


def add_module_info(module: types.ModuleType) -> ModuleInfo:
    """Add ModuleInfo to a module (if not added yet)."""
    if not hasattr(module, '__qute_module_info'):
        module.__qute_module_info = ModuleInfo()
    return module.__qute_module_info


def load_components() -> None:
    """Load everything from qutebrowser.components."""
    for info in walk_components():
        _load_component(info)


def walk_components() -> typing.Iterator[ExtensionInfo]:
    """Yield ExtensionInfo objects for all modules."""
    if hasattr(sys, 'frozen'):
        yield from _walk_pyinstaller()
    else:
        yield from _walk_normal()


def _on_walk_error(name: str) -> None:
    raise ImportError("Failed to import {}".format(name))


def _walk_normal() -> typing.Iterator[ExtensionInfo]:
    """Walk extensions when not using PyInstaller."""
    for _finder, name, ispkg in pkgutil.walk_packages(
            # Only packages have a __path__ attribute,
            # but we're sure this is one.
            path=components.__path__,  # type: ignore
            prefix=components.__name__ + '.',
            onerror=_on_walk_error):
        if ispkg:
            continue
        yield ExtensionInfo(name=name)


def _walk_pyinstaller() -> typing.Iterator[ExtensionInfo]:
    """Walk extensions when using PyInstaller.

    See https://github.com/pyinstaller/pyinstaller/issues/1905

    Inspired by:
    https://github.com/webcomics/dosage/blob/master/dosagelib/loader.py
    """
    toc = set()  # type: typing.Set[str]
    for importer in pkgutil.iter_importers('qutebrowser'):
        if hasattr(importer, 'toc'):
            toc |= importer.toc
    for name in toc:
        if name.startswith(components.__name__ + '.'):
            yield ExtensionInfo(name=name)


def _load_component(info: ExtensionInfo) -> types.ModuleType:
    """Load the given extension and run its init hook (if any)."""
    log.extensions.debug("Importing {}".format(info.name))
    mod = importlib.import_module(info.name)

    info = add_module_info(mod)
    if info.init_hook is not None:
        log.extensions.debug("Running init hook {!r}"
                             .format(info.init_hook.__name__))
        info.init_hook(InitContext())

    return mod
