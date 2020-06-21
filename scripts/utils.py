# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Utility functions for scripts."""

import os
import os.path
import sys


# Import side-effects are an evil thing, but here it's okay so scripts using
# colors work on Windows as well.
try:
    import colorama
except ImportError:
    colorama = None
else:
    colorama.init()


use_color = os.name != 'nt' or colorama


fg_colors = {
    'reset': 0,
    'bold': 1,
    'black': 30,
    'red': 31,
    'green': 32,
    'yellow': 33,
    'blue': 34,
    'magenta': 35,
    'cyan': 36,
    'white': 37,
}


bg_colors = {name: col + 10 for name, col in fg_colors.items()}


def _esc(code):
    """Get an ANSI color code based on a color number."""
    return '\033[{}m'.format(code)


def print_col(text, color, file=sys.stdout):
    """Print a colorized text."""
    if use_color:
        fg = _esc(fg_colors[color.lower()])
        reset = _esc(fg_colors['reset'])
        print(''.join([fg, text, reset]), file=file)
    else:
        print(text, file=file)


def print_error(text):
    print_col(text, 'red', file=sys.stderr)


def print_title(text):
    """Print a title."""
    print()
    print_col("==================== {} ====================".format(text),
              'yellow')


def print_subtitle(text):
    """Print a subtitle."""
    print_col("------ {} ------".format(text), 'cyan')


def change_cwd():
    """Change the scripts cwd if it was started inside the script folder."""
    cwd = os.getcwd()
    if os.path.split(cwd)[1] == 'scripts':
        os.chdir(os.path.join(cwd, os.pardir))
