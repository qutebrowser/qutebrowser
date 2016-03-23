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

"""Utilities related to jinja2."""

import os
import os.path

import jinja2

from qutebrowser.utils import utils

from PyQt5.QtCore import QUrl


class Loader(jinja2.BaseLoader):

    """Jinja loader which uses utils.read_file to load templates.

    Attributes:
        _subdir: The subdirectory to find templates in.
    """

    def __init__(self, subdir):
        self._subdir = subdir

    def get_source(self, _env, template):
        path = os.path.join(self._subdir, template)
        try:
            source = utils.read_file(path)
        except OSError:
            raise jinja2.TemplateNotFound(template)
        # Currently we don't implement auto-reloading, so we always return True
        # for up-to-date.
        return source, path, lambda: True


def _guess_autoescape(template_name):
    """Turn auto-escape on/off based on the file type.

    Based on http://jinja.pocoo.org/docs/dev/api/#autoescaping
    """
    if template_name is None or '.' not in template_name:
        return False
    ext = template_name.rsplit('.', 1)[1]
    return ext in ('html', 'htm', 'xml')


def resource_url(path):
    """Load images from a relative path (to qutebrowser).

    Arguments:
        path: The relative path to the image
    """
    image = utils.resource_filename(path)
    return QUrl.fromLocalFile(image).toString(QUrl.FullyEncoded)


def file_url(path):
    """Return a file:// url (as string) to the given local path.

    Arguments:
        path: The absolute path to the local file
    """
    return QUrl.fromLocalFile(path).toString(QUrl.FullyEncoded)


env = jinja2.Environment(loader=Loader('html'), autoescape=_guess_autoescape)
env.globals['resource_url'] = resource_url
env.globals['file_url'] = file_url
