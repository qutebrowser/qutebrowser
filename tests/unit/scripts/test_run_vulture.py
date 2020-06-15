#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import pytest

from tests.helpers import utils

try:
    from scripts.dev import run_vulture
except ImportError:
    if hasattr(sys, 'frozen'):
        # Tests aren't going to run anyways because of the mark
        pass
    else:
        raise


pytestmark = [pytest.mark.not_frozen]


class VultureDir:

    """Fixture similar to pytest's testdir fixture for vulture.

    Attributes:
        _tmp_path: The pytest tmp_path fixture.
    """

    def __init__(self, tmp_path):
        self._tmp_path = tmp_path

    def run(self):
        """Run vulture over all generated files and return the output."""
        names = [p.name for p in self._tmp_path.glob('*')]
        assert names
        with utils.change_cwd(self._tmp_path):
            return run_vulture.run(names)

    def makepyfile(self, **kwargs):
        """Create a python file, similar to TestDir.makepyfile."""
        for filename, data in kwargs.items():
            text = textwrap.dedent(data)
            (self._tmp_path / (filename + '.py')).write_text(text, 'utf-8')


@pytest.fixture
def vultdir(tmp_path):
    return VultureDir(tmp_path)


def test_used(vultdir):
    vultdir.makepyfile(foo="""
        def foo():
            pass

        foo()
    """)
    assert not vultdir.run()


def test_unused_func(vultdir):
    vultdir.makepyfile(foo="""
        def foo():
            pass
    """)
    msg = "foo.py:2: unused function 'foo' (60% confidence)"
    assert vultdir.run() == [msg]


def test_unused_method_camelcase(vultdir):
    """Should be ignored because those are Qt methods."""
    vultdir.makepyfile(foo="""
        class Foo():

            def fooBar(self):
                pass

        Foo()
    """)
    assert not vultdir.run()
