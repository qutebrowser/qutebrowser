# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities related to the look&feel of qutebrowser.

Module attributes:
    _colordict: The global cached ColorDict.
    _fontdict: The global cached FontDict.
"""

from functools import partial

from PyQt5.QtGui import QColor

import qutebrowser.config.config as config
from qutebrowser.utils.log import style as logger
from qutebrowser.utils.misc import compact_text


_colordict = None
_fontdict = None


def get_stylesheet(template):
    """Format a stylesheet based on a template.

    Args:
        template: The stylesheet template as string.

    Return:
        The formatted template as string.
    """
    global _colordict, _fontdict
    if _colordict is None:
        _colordict = ColorDict(config.section('colors'))
    if _fontdict is None:
        _fontdict = FontDict(config.section('fonts'))
    return template.strip().format(color=_colordict, font=_fontdict,
                                   config=config.instance())


def set_register_stylesheet(obj):
    """Set the stylesheet for an object based on it's STYLESHEET attribute.

    Also, register an update when the config is changed.
    This isn't really good OOP, but it's the cleanest solution I could think
    of.

    Args:
        obj: The object to set the stylesheet for and register.
             Must have a STYLESHEET attribute.
    """
    qss = get_stylesheet(obj.STYLESHEET)
    logger.debug("stylesheet for {}: {}".format(obj.__class__.__name__,
                                                compact_text(qss)))
    obj.setStyleSheet(qss)
    config.instance().changed.connect(partial(_update_stylesheet, obj))


def _update_stylesheet(obj, _section, _option):
    """Update the stylesheet for obj."""
    obj.setStyleSheet(get_stylesheet(obj.STYLESHEET))


def invalidate_caches(section, _option):
    """Invalidate cached dicts."""
    global _colordict, _fontdict
    if section == 'colors':
        _colordict = None
    elif section == 'fonts':
        _fontdict = None


class ColorDict(dict):

    """A dict aimed at Qt stylesheet colors."""

    def __getitem__(self, key):
        """Override dict __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            If a value wasn't found, return an empty string.
            (Color not defined, so no output in the stylesheet)

            If the key has a .fg. element in it, return  color: X;.
            If the key has a .bg. element in it, return  background-color: X;.

            In all other cases, return the plain value.
        """
        try:
            val = super().__getitem__(key)
        except KeyError as e:
            logger.warning("No color defined for {}!".format(e))
            return ''
        if isinstance(val, QColor):
            # This could happen when accidentaly declarding something as
            # QtColor instead of Color in the config, and it'd go unnoticed as
            # the CSS is invalid then.
            raise TypeError("QColor passed to ColorDict!")
        if 'fg' in key.split('.'):
            return 'color: {};'.format(val)
        elif 'bg' in key.split('.'):
            return 'background-color: {};'.format(val)
        else:
            return val

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            A value, or None if the value wasn't found.
        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class FontDict(dict):

    """A dict aimed at Qt stylesheet fonts."""

    def __getitem__(self, key):
        """Override dict __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            If a value wasn't found, return an empty string.
            (Color not defined, so no output in the stylesheet)

            In all other cases, return font: <value>.
        """
        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        else:
            return 'font: {};'.format(val)

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            A value, or None if the value wasn't found.
        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None
