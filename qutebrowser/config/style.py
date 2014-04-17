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

"""Utilities related to the look&feel of qutebrowser."""

from functools import partial

import qutebrowser.config.config as config

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
        _colordict = ColorDict(config.instance['colors'])
    if _fontdict is None:
        _fontdict = FontDict(config.instance['fonts'])
    return template.strip().format(color=_colordict, font=_fontdict)


def set_register_stylesheet(obj):
    """Set the stylesheet for an object based on it's STYLESHEET attribute.

    Also, register an update when the config is changed.
    """
    obj.setStyleSheet(get_stylesheet(obj.STYLESHEET))
    config.instance.changed.connect(partial(_update_stylesheet, obj))


def _update_stylesheet(obj, section, option):
    """Update the stylesheet for obj."""
    # pylint: disable=unused-argument
    obj.setStyleSheet(get_stylesheet(obj.STYLESHEET))


def invalidate_caches(section, option):
    """Invalidate cached dicts."""
    # pylint: disable=unused-argument
    global _colordict, _fontdict
    if section == 'colors':
        _colordict = None
    elif section == 'fonts':
        _fontdict = None


class ColorDict(dict):

    """A dict aimed at Qt stylesheet colors."""

    # FIXME we should validate colors in __setitem__ based on:
    # http://qt-project.org/doc/qt-4.8/stylesheet-reference.html#brush
    # http://www.w3.org/TR/CSS21/syndata.html#color-units

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
        except KeyError:
            return ''
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
