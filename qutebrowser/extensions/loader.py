# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import os
import pkgutil
import types
import typing
import sys
import pathlib

import attr

from PyQt5.QtCore import pyqtSlot

from qutebrowser import components
from qutebrowser.config import config
from qutebrowser.utils import log, standarddir, objreg

MYPY = False
if MYPY:
    # pylint: disable=unused-import,useless-suppression
    import argparse


# ModuleInfo objects for all loaded plugins
_module_infos = []


@attr.s
class InitContext:

    """Context an extension gets in its init hook."""

    data_dir = attr.ib()  # type: pathlib.Path
    config_dir = attr.ib()  # type: pathlib.Path
    args = attr.ib()  # type: argparse.Namespace


@attr.s
class ModuleInfo:

    """Information attached to an extension module.

    This gets used by qutebrowser.api.hook.
    """

    _ConfigChangedHooksType = typing.List[typing.Tuple[typing.Optional[str],
                                                       typing.Callable]]

    skip_hooks = attr.ib(False)  # type: bool
    init_hook = attr.ib(None)  # type: typing.Optional[typing.Callable]
    config_changed_hooks = attr.ib(
        attr.Factory(list))  # type: _ConfigChangedHooksType


@attr.s
class ExtensionInfo:

    """Information about a qutebrowser extension."""

    name = attr.ib()  # type: str


def add_module_info(module: types.ModuleType) -> ModuleInfo:
    """Add ModuleInfo to a module (if not added yet)."""
    # pylint: disable=protected-access
    if not hasattr(module, '__qute_module_info'):
        module.__qute_module_info = ModuleInfo()  # type: ignore
    return module.__qute_module_info  # type: ignore


def load_components(*, skip_hooks: bool = False) -> None:
    """Load everything from qutebrowser.components."""
    for info in walk_components():
        _load_component(info, skip_hooks=skip_hooks)
    for info in walk_extensions():
        _load_component(info, skip_hooks=skip_hooks)


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


def walk_extensions() -> typing.Iterator[ExtensionInfo]:
    """Walk external extensions."""
    ext_dir = os.path.join(standarddir.data(), 'extensions')
    if not os.path.exists(ext_dir):
        try:
            os.mkdir(ext_dir)
        except OSError:
            pass
        return

    if os.listdir(ext_dir):
        log.extensions.warning(
            "Loading EXTENSIONS in {}: this in an "
            "EXPERIMENTAL FEATURE.".format(ext_dir)
        )
    else:
        return

    prefix = 'qutebrowser.extensions.third_party.'
    for finder, name, _ispkg in pkgutil.walk_packages(
            path=[ext_dir],
            prefix=prefix,
            onerror=_on_walk_error):
        if name not in sys.modules:
            try:
                # Import the module with the finder so that it is in
                # sys.modules ready for _load_component.
                finder.find_module(name).load_module(name)
            except Exception:
                log.extensions.exception(
                    "Exception while importing extension: {}"
                    .format(name[len(prefix):])
                )
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


def _get_init_context() -> InitContext:
    """Get an InitContext object."""
    return InitContext(data_dir=pathlib.Path(standarddir.data()),
                       config_dir=pathlib.Path(standarddir.config()),
                       args=objreg.get('args'))


def _load_component(
        info: ExtensionInfo, *,
        skip_hooks: bool = False) -> typing.Optional[types.ModuleType]:
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
        try:
            mod_info.init_hook(_get_init_context())
        except Exception:
            log.extensions.exception(
                "Exception while initializing extension: {}"
                .format(mod.__file__)
            )
            return None

    _module_infos.append(mod_info)

    return mod


@pyqtSlot(str)
def _on_config_changed(changed_name: str) -> None:
    """Call config_changed hooks if the config changed."""
    for mod_info in _module_infos:
        if mod_info.skip_hooks:
            continue
        for option, hook in mod_info.config_changed_hooks:
            try:
                if option is None:
                    hook()
                else:
                    cfilter = config.change_filter(option)
                    cfilter.validate()
                    if cfilter.check_match(changed_name):
                        hook()
            except Exception:
                log.extensions.exception(
                    "Exception while running config change hook for "
                    "item {} in extension: {}".format(
                        changed_name, hook.__code__.co_filename,
                    )
                )


def init() -> None:
    config.instance.changed.connect(_on_config_changed)
