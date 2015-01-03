#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import os.path
import sys
import subprocess
import glob
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from scripts import utils


def call_asciidoc(src, dst):
    """Call asciidoc for the given files.

    Args:
        src: The source .asciidoc file.
        dst: The destination .html file, or None to auto-guess.
    """
    print("Calling asciidoc for {}...".format(os.path.basename(src)))
    if os.name == 'nt':
        # FIXME this is highly specific to my machine
        # https://github.com/The-Compiler/qutebrowser/issues/106
        args = [r'C:\Python27\python', r'J:\bin\asciidoc-8.6.9\asciidoc.py']
    else:
        args = ['asciidoc']
    if dst is not None:
        args += ['--out-file', dst]
    args.append(src)
    try:
        subprocess.check_call(args)
    except FileNotFoundError:
        utils.print_col("asciidoc needs to be installed to use this script!",
                        'red')
        sys.exit(1)
    except (subprocess.CalledProcessError, OSError) as e:
        utils.print_col(str(e), 'red')
        sys.exit(1)


def main(colors=False):
    """Generate html files for the online documentation."""
    utils.change_cwd()
    utils.use_color = colors
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', help="Build all documentation into a given "
                        "directory.", nargs=1)
    args = parser.parse_args()
    asciidoc_files = [
        ('doc/FAQ.asciidoc', 'qutebrowser/html/doc/FAQ.html'),
        ('doc/quickstart.asciidoc', 'qutebrowser/html/doc/quickstart.html'),
    ]
    try:
        os.mkdir('qutebrowser/html/doc')
    except FileExistsError:
        pass
    if args.all:
        for root, _dirs, files in os.walk(os.getcwd()):
            for filename in files:
                if os.path.splitext(filename)[1] != '.asciidoc':
                    continue
                src = os.path.join(root, filename)
                parts = [args.all[0]]
                dirname = os.path.dirname(src)
                if dirname:
                    parts.append(os.path.relpath(os.path.dirname(src)))
                parts.append(
                    os.extsep.join((os.path.splitext(os.path.basename(src))[0],
                                    'html')))
                dst = os.path.join(*parts)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                call_asciidoc(src, dst)
    else:
        for src in glob.glob('doc/help/*.asciidoc'):
            name, _ext = os.path.splitext(os.path.basename(src))
            dst = 'qutebrowser/html/doc/{}.html'.format(name)
            asciidoc_files.append((src, dst))
        for src, dst in asciidoc_files:
            call_asciidoc(src, dst)


if __name__ == '__main__':
    main(colors=True)
