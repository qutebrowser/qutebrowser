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


class AsciiDoc:

    """Abstraction of an asciidoc subprocess."""

    FILES = [
        ('FAQ.asciidoc', 'qutebrowser/html/doc/FAQ.html'),
        ('CHANGELOG.asciidoc', 'qutebrowser/html/doc/CHANGELOG.html'),
        ('doc/quickstart.asciidoc', 'qutebrowser/html/doc/quickstart.html'),
        ('doc/userscripts.asciidoc', 'qutebrowser/html/doc/userscripts.html'),
    ]

    def __init__(self, args):
        self._cmd = None
        self._args = args

    def prepare(self):
        """Get the asciidoc command and create the homedir to use."""
        self._cmd = self._get_asciidoc_cmd()

    def build(self):
        if self._args.website:
            self._build_website()
        else:
            self._build_docs()

    def _build_docs(self):
        files = self.FILES[:]
        for src in glob.glob('doc/help/*.asciidoc'):
            name, _ext = os.path.splitext(os.path.basename(src))
            dst = 'qutebrowser/html/doc/{}.html'.format(name)
            files.append((src, dst))
        for src, dst in files:
            self.call(src, dst)

    def _build_website(self):
        for root, _dirs, files in os.walk(os.getcwd()):
            for filename in files:
                if os.path.splitext(filename)[1] != '.asciidoc':
                    continue
                src = os.path.join(root, filename)
                parts = [self._args.all[0]]
                dirname = os.path.dirname(src)
                if dirname:
                    parts.append(os.path.relpath(os.path.dirname(src)))
                parts.append(
                    os.extsep.join((os.path.splitext(os.path.basename(src))[0],
                                    'html')))
                dst = os.path.join(*parts)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                self.call(src, dst)

    def _get_asciidoc_cmd(self):
        """Try to find out what commandline to use to invoke asciidoc."""
        if self._args.asciidoc is not None:
            return self._args.asciidoc

        try:
            subprocess.call(['asciidoc'], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except OSError:
            pass
        else:
            return ['asciidoc']

        try:
            subprocess.call(['asciidoc.py'], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except OSError:
            pass
        else:
            return ['asciidoc.py']

        raise FileNotFoundError

    def call(self, src, dst, theme=None):
        """Call asciidoc for the given files.

        Args:
            src: The source .asciidoc file.
            dst: The destination .html file, or None to auto-guess.
            theme: The CSS to use as a theme.
        """
        print("Calling asciidoc for {}...".format(os.path.basename(src)))
        args = self._cmd[:]
        if dst is not None:
            args += ['--out-file', dst]
        args.append(src)
        try:
            subprocess.check_call(args)
        except (subprocess.CalledProcessError, OSError) as e:
            utils.print_col(str(e), 'red')
            sys.exit(1)


def main(colors=False):
    """Generate html files for the online documentation."""
    utils.change_cwd()
    utils.use_color = colors
    parser = argparse.ArgumentParser()
    parser.add_argument('--website', help="Build website into a given "
                        "directory.", nargs=1)
    parser.add_argument('--asciidoc', help="Full path to python and "
                        "asciidoc.py. If not given, it's searched in PATH.",
                        nargs=2, required=False,
                        metavar=('PYTHON', 'ASCIIDOC'))
    args = parser.parse_args()
    try:
        os.mkdir('qutebrowser/html/doc')
    except FileExistsError:
        pass

    asciidoc = AsciiDoc(args)
    try:
        asciidoc.prepare()
    except FileNotFoundError:
        utils.print_col("Could not find asciidoc! Please install it, or use "
                        "the --asciidoc argument to point this script to the "
                        "correct python/asciidoc.py location!", 'red')
        sys.exit(1)
    asciidoc.build()


if __name__ == '__main__':
    main(colors=True)
