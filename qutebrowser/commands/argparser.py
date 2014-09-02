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

"""argparse.ArgumentParser subclass to parse qutebrowser commands."""

import argparse


class ArgumentParserError(Exception):

    """Exception raised when the ArgumentParser signals an error."""


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self):
        super().__init__(add_help=False)

    def exit(self, status=0, msg=None):
        raise AssertionError('exit called, this should never happen. '
                             'Status: {}, message: {}'.format(status, msg))

    def error(self, msg):
        raise ArgumentParserError(msg)
