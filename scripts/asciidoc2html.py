#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import re
import os
import os.path
import sys
import subprocess
import glob
import shutil
import tempfile
import argparse
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from scripts import utils


class AsciiDoc:

    """Abstraction of an asciidoc subprocess."""

    FILES = [
        ('FAQ.asciidoc', 'qutebrowser/html/doc/FAQ.html'),
        ('CHANGELOG.asciidoc', 'qutebrowser/html/doc/CHANGELOG.html'),
        ('CONTRIBUTING.asciidoc', 'qutebrowser/html/doc/CONTRIBUTING.html'),
        ('doc/quickstart.asciidoc', 'qutebrowser/html/doc/quickstart.html'),
        ('doc/userscripts.asciidoc', 'qutebrowser/html/doc/userscripts.html'),
    ]

    def __init__(self, args):
        self._cmd = None
        self._args = args
        self._homedir = None
        self._themedir = None
        self._tempdir = None
        self._failed = False

    def prepare(self):
        """Get the asciidoc command and create the homedir to use."""
        self._cmd = self._get_asciidoc_cmd()
        self._homedir = tempfile.mkdtemp()
        self._themedir = os.path.join(
            self._homedir, '.asciidoc', 'themes', 'qute')
        self._tempdir = os.path.join(self._homedir, 'tmp')
        os.makedirs(self._tempdir)
        os.makedirs(self._themedir)

    def cleanup(self):
        """Clean up the temporary home directory for asciidoc."""
        if self._homedir is not None and not self._failed:
            shutil.rmtree(self._homedir)

    def build(self):
        if self._args.website:
            self._build_website()
        else:
            self._build_docs()
            self._copy_images()

    def _build_docs(self):
        """Render .asciidoc files to .html sites."""
        files = self.FILES[:]
        for src in glob.glob('doc/help/*.asciidoc'):
            name, _ext = os.path.splitext(os.path.basename(src))
            dst = 'qutebrowser/html/doc/{}.html'.format(name)
            files.append((src, dst))

        # patch image links to use local copy
        replacements = [
            ("http://qutebrowser.org/img/cheatsheet-big.png",
                "qute://help/img/cheatsheet-big.png"),
            ("http://qutebrowser.org/img/cheatsheet-small.png",
                "qute://help/img/cheatsheet-small.png")
        ]

        for src, dst in files:
            src_basename = os.path.basename(src)
            modified_src = os.path.join(self._tempdir, src_basename)
            with open(modified_src, 'w', encoding='utf-8') as modified_f, \
                    open(src, 'r', encoding='utf-8') as f:
                for line in f:
                    for orig, repl in replacements:
                        line = line.replace(orig, repl)
                    modified_f.write(line)
            self.call(modified_src, dst)

    def _copy_images(self):
        """Copy image files to qutebrowser/html/doc."""
        print("Copying files...")
        dst_path = os.path.join('qutebrowser', 'html', 'doc', 'img')
        try:
            os.mkdir(dst_path)
        except FileExistsError:
            pass
        for filename in ['cheatsheet-big.png', 'cheatsheet-small.png']:
            src = os.path.join('doc', 'img', filename)
            dst = os.path.join(dst_path, filename)
            shutil.copy(src, dst)

    def _build_website_file(self, root, filename):
        """Build a single website file."""
        # pylint: disable=too-many-locals,too-many-statements
        src = os.path.join(root, filename)
        src_basename = os.path.basename(src)
        parts = [self._args.website[0]]
        dirname = os.path.dirname(src)
        if dirname:
            parts.append(os.path.relpath(os.path.dirname(src)))
        parts.append(
            os.extsep.join((os.path.splitext(src_basename)[0],
                            'html')))
        dst = os.path.join(*parts)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        modified_src = os.path.join(self._tempdir, src_basename)
        shutil.copy('www/header.asciidoc', modified_src)

        outfp = io.StringIO()

        with open(modified_src, 'r', encoding='utf-8') as header_file:
            header = header_file.read()
            header += "\n\n"

        with open(src, 'r', encoding='utf-8') as infp:
            outfp.write("\n\n")
            hidden = False
            found_title = False
            title = ""
            last_line = ""

            for line in infp:
                if line.strip() == '// QUTE_WEB_HIDE':
                    assert not hidden
                    hidden = True
                elif line.strip() == '// QUTE_WEB_HIDE_END':
                    assert hidden
                    hidden = False
                elif line == "The Compiler <mail@qutebrowser.org>\n":
                    continue
                elif re.match(r'^:\w+:.*', line):
                    # asciidoc field
                    continue

                if not found_title:
                    if re.match(r'^=+$', line):
                        line = line.replace('=', '-')
                        found_title = True
                        title = last_line.rstrip('\n') + " | qutebrowser\n"
                        title += "=" * (len(title) - 1)
                    elif re.match(r'^= .+', line):
                        line = '==' + line[1:]
                        found_title = True
                        title = last_line.rstrip('\n') + " | qutebrowser\n"
                        title += "=" * (len(title) - 1)

                if not hidden:
                    outfp.write(line.replace(".asciidoc[", ".html["))
                    last_line = line

        current_lines = outfp.getvalue()
        outfp.close()

        with open(modified_src, 'w+', encoding='utf-8') as final_version:
            final_version.write(title + "\n\n" + header + current_lines)

        self.call(modified_src, dst, '--theme=qute')

    def _build_website(self):
        """Prepare and build the website."""
        theme_file = os.path.abspath(os.path.join('www', 'qute.css'))
        shutil.copy(theme_file, self._themedir)

        outdir = self._args.website[0]

        for root, _dirs, files in os.walk(os.getcwd()):
            for filename in files:
                basename, ext = os.path.splitext(filename)
                if (ext != '.asciidoc' or
                        basename in ['header', 'OpenSans-License']):
                    continue
                self._build_website_file(root, filename)

        copy = {'icons': 'icons', 'doc/img': 'doc/img', 'www/media': 'media/'}

        for src, dest in copy.items():
            full_dest = os.path.join(outdir, dest)
            try:
                shutil.rmtree(full_dest)
            except FileNotFoundError:
                pass
            shutil.copytree(src, full_dest)

        for dst, link_name in [
            ('README.html', 'index.html'),
            (os.path.join('doc', 'quickstart.html'), 'quickstart.html'),
        ]:
            try:
                os.symlink(dst, os.path.join(outdir, link_name))
            except FileExistsError:
                pass

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

    def call(self, src, dst, *args):
        """Call asciidoc for the given files.

        Args:
            src: The source .asciidoc file.
            dst: The destination .html file, or None to auto-guess.
            *args: Additional arguments passed to asciidoc.
        """
        print("Calling asciidoc for {}...".format(os.path.basename(src)))
        cmdline = self._cmd[:]
        if dst is not None:
            cmdline += ['--out-file', dst]
        cmdline += args
        cmdline.append(src)
        try:
            env = os.environ.copy()
            env['HOME'] = self._homedir
            subprocess.check_call(cmdline, env=env)
            self._failed = True
        except (subprocess.CalledProcessError, OSError) as e:
            self._failed = True
            utils.print_col(str(e), 'red')
            print("Keeping modified sources in {}.".format(self._homedir))
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
    parser.add_argument('--no-authors', help=argparse.SUPPRESS,
                        action='store_true')
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

    try:
        asciidoc.build()
    finally:
        asciidoc.cleanup()


if __name__ == '__main__':
    main(colors=True)
