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

import sys
import textwrap

import pytest_bdd as bdd
bdd.scenarios('editor.feature')


@bdd.when(bdd.parsers.parse('I set up a fake editor replacing "{text}" by '
                            '"{replacement}"'))
def set_up_editor_replacement(quteproc, httpbin, tmpdir, text, replacement):
    """Set up general->editor to a small python script doing a replacement."""
    text = text.replace('(port)', str(httpbin.port))
    script = tmpdir / 'script.py'
    script.write(textwrap.dedent("""
        import sys

        with open(sys.argv[1], encoding='utf-8') as f:
            data = f.read()

        data = data.replace("{text}", "{replacement}")

        with open(sys.argv[1], 'w', encoding='utf-8') as f:
            f.write(data)
    """.format(text=text, replacement=replacement)))
    editor = '"{}" "{}" {{}}'.format(sys.executable, script)
    quteproc.set_setting('general', 'editor', editor)


@bdd.when(bdd.parsers.parse('I set up a fake editor returning "{text}"'))
def set_up_editor(quteproc, httpbin, tmpdir, text):
    """Set up general->editor to a small python script inserting a text."""
    script = tmpdir / 'script.py'
    script.write(textwrap.dedent("""
        import sys

        with open(sys.argv[1], 'w', encoding='utf-8') as f:
            f.write({text!r})
    """.format(text=text)))
    editor = '"{}" "{}" {{}}'.format(sys.executable, script)
    quteproc.set_setting('general', 'editor', editor)
