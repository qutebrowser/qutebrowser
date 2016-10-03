# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools
import collections

import jinja2
import sip
from PyQt5.QtGui import QColor

from qutebrowser.config import config
from qutebrowser.utils import log, objreg


@functools.lru_cache(maxsize=16)
def get_stylesheet(template_str):
    """Format a stylesheet based on a template.

    Args:
        template_str: The stylesheet template as string.

    Return:
        The formatted template as string.
    """
    colordict = ColorDict(config.section('colors'))
    template = jinja2.Template(template_str)
    return template.render(color=colordict, font=config.section('fonts'),
                           config=objreg.get('config'))


def set_register_stylesheet(obj):
    """Set the stylesheet for an object based on it's STYLESHEET attribute.

    Also, register an update when the config is changed.

    Args:
        obj: The object to set the stylesheet for and register.
             Must have a STYLESHEET attribute.
    """
    qss = get_stylesheet(obj.STYLESHEET)
    log.config.vdebug("stylesheet for {}: {}".format(
        obj.__class__.__name__, qss))
    obj.setStyleSheet(qss)
    objreg.get('config').changed.connect(
        functools.partial(_update_stylesheet, obj))


def _update_stylesheet(obj):
    """Update the stylesheet for obj."""
    get_stylesheet.cache_clear()
    if not sip.isdeleted(obj):
        obj.setStyleSheet(get_stylesheet(obj.STYLESHEET))


class ColorDict(collections.UserDict):

    """A dict aimed at Qt stylesheet colors."""

    def __getitem__(self, key):
        """Override dict __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            If a value wasn't found, return an empty string.
            (Color not defined, so no output in the stylesheet)

            else, return the plain value.
        """
        try:
            val = self.data[key]
        except KeyError:
            log.config.exception("No color defined for {}!".format(key))
            return ''
        if isinstance(val, QColor):
            # This could happen when accidentally declaring something as
            # QtColor instead of Color in the config, and it'd go unnoticed as
            # the CSS is invalid then.
            raise TypeError("QColor passed to ColorDict!")
        else:
            return val
