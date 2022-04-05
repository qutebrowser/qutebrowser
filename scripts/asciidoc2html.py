#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Generate the html documentation based on the asciidoc files."""

from typing import List, Optional
import re
import os
import sys
import subprocess
import shutil
import tempfile
import argparse
import io
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC_DIR = REPO_ROOT / 'qutebrowser' / 'html' / 'doc'

sys.path.insert(0, str(REPO_ROOT))

from scripts import utils


class AsciiDoc:

    """Abstraction of an asciidoc subprocess."""

    FILES = ['faq', 'changelog', 'contributing', 'quickstart', 'userscripts']

    def __init__(self,
                 asciidoc: Optional[str],
                 asciidoc_python: Optional[str],
                 website: Optional[str]) -> None:
        self._cmd: Optional[List[str]] = None
        self._asciidoc = asciidoc
        self._asciidoc_python = asciidoc_python
        self._website = website
        self._homedir: Optional[pathlib.Path] = None
        self._themedir: Optional[pathlib.Path] = None
        self._tempdir: Optional[pathlib.Path] = None
        self._failed = False

    def prepare(self) -> None:
        """Get the asciidoc command and create the homedir to use."""
        self._cmd = self._get_asciidoc_cmd()
        self._homedir = pathlib.Path(tempfile.mkdtemp())
        self._themedir = self._homedir / '.asciidoc' / 'themes' / 'qute'
        self._tempdir = self._homedir / 'tmp'
        self._tempdir.mkdir(parents=True)
        self._themedir.mkdir(parents=True)

    def cleanup(self) -> None:
        """Clean up the temporary home directory for asciidoc."""
        if self._homedir is not None and not self._failed:
            shutil.rmtree(str(self._homedir))

    def build(self) -> None:
        """Build either the website or the docs."""
        if self._website:
            self._build_website()
        else:
            self._build_docs()
            self._copy_images()

    def _build_docs(self) -> None:
        """Render .asciidoc files to .html sites."""
        files = [((REPO_ROOT / 'doc' / '{}.asciidoc'.format(f)),
                  DOC_DIR / (f + ".html")) for f in self.FILES]
        for src in (REPO_ROOT / 'doc' / 'help').glob('*.asciidoc'):
            dst = DOC_DIR / (src.stem + ".html")
            files.append((src, dst))

        # patch image links to use local copy
        replacements = [
            ("https://raw.githubusercontent.com/qutebrowser/qutebrowser/master/doc/img/cheatsheet-big.png",
             "qute://help/img/cheatsheet-big.png"),
            ("https://raw.githubusercontent.com/qutebrowser/qutebrowser/master/doc/img/cheatsheet-small.png",
             "qute://help/img/cheatsheet-small.png")
        ]
        asciidoc_args = ['-a', 'source-highlighter=pygments']

        for src, dst in files:
            assert self._tempdir is not None    # for mypy
            modified_src = self._tempdir / src.name
            with modified_src.open('w', encoding='utf-8') as moded_f, \
                    src.open('r', encoding='utf-8') as f:
                for line in f:
                    for orig, repl in replacements:
                        line = line.replace(orig, repl)
                    moded_f.write(line)
            self.call(modified_src, dst, *asciidoc_args)

    def _copy_images(self) -> None:
        """Copy image files to qutebrowser/html/doc."""
        print("Copying files...")
        dst_path = DOC_DIR / 'img'
        dst_path.mkdir(exist_ok=True)
        for filename in ['cheatsheet-big.png', 'cheatsheet-small.png']:
            src = REPO_ROOT / 'doc' / 'img' / filename
            dst = dst_path / filename
            shutil.copy(str(src), str(dst))

    def _build_website_file(self, root: pathlib.Path, filename: str) -> None:
        """Build a single website file."""
        src = root / filename
        assert self._website is not None    # for mypy
        dst = pathlib.Path(self._website)
        dst = dst / src.parent.relative_to(REPO_ROOT) / (src.stem + ".html")
        dst.parent.mkdir(exist_ok=True)

        assert self._tempdir is not None    # for mypy
        modified_src = self._tempdir / src.name
        shutil.copy(str(REPO_ROOT / 'www' / 'header.asciidoc'), modified_src)

        outfp = io.StringIO()

        header = modified_src.read_text(encoding='utf-8')
        header += "\n\n"

        with src.open('r', encoding='utf-8') as infp:
            outfp.write("\n\n")
            hidden = False
            found_title = False
            title = ""
            last_line = ""

            for line in infp:
                line = line.rstrip()
                if line == '// QUTE_WEB_HIDE':
                    assert not hidden
                    hidden = True
                elif line == '// QUTE_WEB_HIDE_END':
                    assert hidden
                    hidden = False
                elif line == "The Compiler <mail@qutebrowser.org>":
                    continue
                elif re.fullmatch(r':\w+:.*', line):
                    # asciidoc field
                    continue

                if not found_title:
                    if re.fullmatch(r'=+', line):
                        line = line.replace('=', '-')
                        found_title = True
                        title = last_line + " | qutebrowser\n"
                        title += "=" * (len(title) - 1)
                    elif re.fullmatch(r'= .+', line):
                        line = '==' + line[1:]
                        found_title = True
                        title = last_line + " | qutebrowser\n"
                        title += "=" * (len(title) - 1)

                if not hidden:
                    outfp.write(line.replace(".asciidoc[", ".html[") + '\n')
                    last_line = line

        current_lines = outfp.getvalue()
        outfp.close()

        modified_str = title + "\n\n" + header + current_lines
        modified_src.write_text(modified_str, encoding='utf-8')

        asciidoc_args = ['--theme=qute', '-a toc', '-a toc-placement=manual',
                         '-a', 'source-highlighter=pygments']
        self.call(modified_src, dst, *asciidoc_args)

    def _build_website(self) -> None:
        """Prepare and build the website."""
        theme_file = REPO_ROOT / 'www' / 'qute.css'
        assert self._themedir is not None   # for mypy
        shutil.copy(theme_file, self._themedir)

        assert self._website is not None    # for mypy
        outdir = pathlib.Path(self._website)

        for item_path in pathlib.Path(REPO_ROOT).rglob('*.asciidoc'):
            if item_path.stem in ['header', 'OpenSans-License']:
                continue
            self._build_website_file(item_path.parent, item_path.name)

        copy = {
            'qutebrowser/icons': 'icons',
            'doc/img': 'doc/img',
            'www/media': 'media/',
        }

        for src, dest in copy.items():
            full_src = REPO_ROOT / src
            full_dest = outdir / dest
            try:
                shutil.rmtree(full_dest)
            except FileNotFoundError:
                pass
            shutil.copytree(full_src, full_dest)

        for dst, link_name in [
                ('README.html', 'index.html'),
                ((pathlib.Path('doc') / 'quickstart.html'), 'quickstart.html'),
        ]:
            assert isinstance(dst, (str, pathlib.Path))    # for mypy
            try:
                (outdir / link_name).symlink_to(dst)
            except FileExistsError:
                pass

    def _get_asciidoc_cmd(self) -> List[str]:
        """Try to find out what commandline to use to invoke asciidoc."""
        if self._asciidoc is not None:
            python = (sys.executable if self._asciidoc_python is None
                      else self._asciidoc_python)
            return [python, self._asciidoc]

        for executable in ['asciidoc', 'asciidoc.py']:
            try:
                subprocess.run([executable, '--version'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               check=True)
            except OSError:
                pass
            else:
                return [executable]

        raise FileNotFoundError

    def call(self, src: pathlib.Path, dst: pathlib.Path, *args):
        """Call asciidoc for the given files.

        Args:
            src: The source .asciidoc file.
            dst: The destination .html file, or None to auto-guess.
            *args: Additional arguments passed to asciidoc.
        """
        print("Calling asciidoc for {}...".format(src.name))
        assert self._cmd is not None    # for mypy
        cmdline = self._cmd[:]
        if dst is not None:
            cmdline += ['--out-file', str(dst)]
        cmdline += args
        cmdline.append(str(src))

        # So the virtualenv's Pygments is found
        bin_path = pathlib.Path(sys.executable).parent

        try:
            env = os.environ.copy()
            env['HOME'] = str(self._homedir)
            env['PATH'] = str(bin_path) + os.pathsep + env['PATH']
            subprocess.run(cmdline, check=True, env=env)
        except (subprocess.CalledProcessError, OSError) as e:
            self._failed = True
            utils.print_error(str(e))
            print("Keeping modified sources in {}.".format(self._homedir),
                  file=sys.stderr)
            sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--website', help="Build website into a given "
                        "directory.")
    parser.add_argument('--asciidoc', help="Full path to asciidoc.py. "
                        "If not given, it's searched in PATH.",
                        nargs='?')
    parser.add_argument('--asciidoc-python', help="Python to use for asciidoc."
                        "If not given, the current Python interpreter is used.",
                        nargs='?')
    return parser.parse_args()


def run(**kwargs) -> None:
    """Regenerate documentation."""
    DOC_DIR.mkdir(exist_ok=True)

    asciidoc = AsciiDoc(**kwargs)
    try:
        asciidoc.prepare()
    except FileNotFoundError:
        utils.print_error("Could not find asciidoc! Please install it, or use "
                          "the --asciidoc argument to point this script to "
                          "the correct asciidoc.py location!")
        sys.exit(1)

    try:
        asciidoc.build()
    finally:
        asciidoc.cleanup()


def main(colors: bool = False) -> None:
    """Generate html files for the online documentation."""
    utils.change_cwd()
    utils.use_color = colors
    args = parse_args()
    run(asciidoc=args.asciidoc, asciidoc_python=args.asciidoc_python,
        website=args.website)


if __name__ == '__main__':
    main(colors=True)
