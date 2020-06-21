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

"""Handling of Qt qss stylesheets."""

import functools
from typing import Optional, FrozenSet

from PyQt5.QtCore import pyqtSlot, QObject

from qutebrowser.config import config
from qutebrowser.misc import debugcachestats
from qutebrowser.utils import jinja, log


def set_register(obj: QObject,
                 stylesheet: str = None, *,
                 update: bool = True) -> None:
    """Set the stylesheet for an object.

    Also, register an update when the config is changed.

    Args:
        obj: The object to set the stylesheet for and register.
             Must have a STYLESHEET attribute if stylesheet is not given.
        stylesheet: The stylesheet to use.
        update: Whether to update the stylesheet on config changes.
    """
    observer = _StyleSheetObserver(obj, stylesheet, update)
    observer.register()


@debugcachestats.register()
@functools.lru_cache()
def _render_stylesheet(stylesheet: str) -> str:
    """Render the given stylesheet jinja template."""
    with jinja.environment.no_autoescape():
        template = jinja.environment.from_string(stylesheet)
    return template.render(conf=config.val)


def init() -> None:
    config.instance.changed.connect(_render_stylesheet.cache_clear)


class _StyleSheetObserver(QObject):

    """Set the stylesheet on the given object and update it on changes.

    Attributes:
        _obj: The object to observe.
        _stylesheet: The stylesheet template to use.
        _options: The config options that the stylesheet uses. When it's not
                  necessary to listen for config changes, this attribute may be
                  None.
    """

    def __init__(self, obj: QObject,
                 stylesheet: Optional[str], update: bool) -> None:
        super().__init__()
        self._obj = obj
        self._update = update

        # We only need to hang around if we are asked to update.
        if update:
            self.setParent(self._obj)
        if stylesheet is None:
            self._stylesheet = obj.STYLESHEET  # type: str
        else:
            self._stylesheet = stylesheet

        if update:
            self._options = jinja.template_config_variables(
                self._stylesheet)  # type: Optional[FrozenSet[str]]
        else:
            self._options = None

    def _get_stylesheet(self) -> str:
        """Format a stylesheet based on a template.

        Return:
            The formatted template as string.
        """
        return _render_stylesheet(self._stylesheet)

    @pyqtSlot(str)
    def _maybe_update_stylesheet(self, option: str) -> None:
        """Update the stylesheet for obj if the option changed affects it."""
        assert self._options is not None
        if option in self._options:
            self._obj.setStyleSheet(self._get_stylesheet())

    def register(self) -> None:
        """Do a first update and listen for more."""
        qss = self._get_stylesheet()
        log.config.vdebug(  # type: ignore[attr-defined]
            "stylesheet for {}: {}".format(self._obj.__class__.__name__, qss))
        self._obj.setStyleSheet(qss)
        if self._update:
            config.instance.changed.connect(self._maybe_update_stylesheet)
