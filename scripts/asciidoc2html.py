#!/usr/bin/python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Generate the html documentation based on the asciidoc files."""

import os
import sys
import subprocess
import glob

sys.path.insert(0, os.getcwd())

from scripts import utils


def call_asciidoc(src, dst):
    """Call asciidoc for the given files.

    Args:
        src: The source .asciidoc file.
        dst: The destination .html file, or None to auto-guess.
    """
    utils.print_col("Calling asciidoc for {}...".format(
        os.path.basename(src)), 'cyan')
    if os.name == 'nt':
        # FIXME this is highly specific to my machine
        args = [r'C:\Python27\python', r'J:\bin\asciidoc-8.6.9\asciidoc.py']
    else:
        args = ['asciidoc']
    if dst is not None:
        args += ['--out-file', dst]
    args.append(src)
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as e:
        utils.print_col(str(e), 'red')
        sys.exit(1)


def main(colors=False):
    """Generate html files for the online documentation."""
    utils.use_color = colors
    asciidoc_files = [
        ('doc/FAQ.asciidoc', 'qutebrowser/html/doc/FAQ.html'),
    ]
    try:
        os.mkdir('qutebrowser/html/doc')
    except FileExistsError:
        pass
    for src in glob.glob('doc/help/*.asciidoc'):
        name, _ext = os.path.splitext(os.path.basename(src))
        dst = 'qutebrowser/html/doc/{}.html'.format(name)
        asciidoc_files.append((src, dst))
    for src, dst in asciidoc_files:
        call_asciidoc(src, dst)


if __name__ == '__main__':
    main(colors=True)
