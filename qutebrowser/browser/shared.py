# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various utilities shared between webpage/webview subclasses."""


from PyQt5.QtWidgets import QFileDialog


class UseSuper(Exception):

    """Exception raised when the caller should do a super() call."""


def choose_file(suggested_name):
    """Prompt the user for a filename and return it."""
    filename, _filter = QFileDialog.getOpenFileName(None, None, suggested_name)
    return filename


def choose_files(suggested_name):
    """Prompt the user for multiple filenames and return them."""
    filenames, _filter = QFileDialog.getOpenFileNames(None, None,
                                                      suggested_name)
    return filenames
