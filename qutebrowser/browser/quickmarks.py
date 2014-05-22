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

"""Manager for quickmarks."""

from functools import partial
from collections import OrderedDict

from PyQt5.QtCore import QStandardPaths

import qutebrowser.utils.message as message
import qutebrowser.commands.utils as cmdutils
from qutebrowser.utils.usertypes import PromptMode
from qutebrowser.config.lineparser import LineConfigParser
from qutebrowser.utils.misc import get_standard_dir
from qutebrowser.utils.url import urlstring
from qutebrowser.commands.exceptions import CommandError


marks = OrderedDict()
linecp = None


def init():
    """Read quickmarks from the config file."""
    global marks, linecp
    confdir = get_standard_dir(QStandardPaths.ConfigLocation)
    linecp = LineConfigParser(confdir, 'quickmarks')
    for line in linecp:
        key, url = line.split(maxsplit=1)
        marks[key] = url


def save():
    """Save the quickmarks to disk."""
    linecp.data = [' '.join(tpl) for tpl in marks.items()]
    linecp.save()


def prompt_save(url):
    """Prompt for a new quickmark name to be added and add it."""
    message.question("Add quickmark:", PromptMode.text,
                     partial(quickmark_add, url))


@cmdutils.register()
def quickmark_add(url, name):
    """Add a new quickmark.

    Args:
        url: The url to add as quickmark.
        name: The name for the new quickmark.
    """
    if not name:
        raise CommandError("Can't set mark with empty name!")
    if not url:
        raise CommandError("Can't set mark with empty URL!")

    def set_mark():
        marks[name] = urlstring(url)

    if name in marks:
        message.confirm_action("Override existing quickmark?", set_mark,
                               default=True)
    else:
        set_mark()


def get(name):
    """Get the URL of the quickmark named name."""
    if name not in marks:
        raise CommandError("Quickmark '{}' does not exist!".format(name))
    return marks[name]
