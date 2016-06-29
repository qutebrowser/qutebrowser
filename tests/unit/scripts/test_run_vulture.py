#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
        _tmpdir: The pytest tmpdir fixture.
    """

    def __init__(self, tmpdir):
        self._tmpdir = tmpdir

    def run(self):
        """Run vulture over all generated files and return the output."""
        files = self._tmpdir.listdir()
        assert files
        with self._tmpdir.as_cwd():
            return run_vulture.run([str(e.basename) for e in files])

    def makepyfile(self, **kwargs):
        """Create a python file, similar to TestDir.makepyfile."""
        for filename, data in kwargs.items():
            text = textwrap.dedent(data)
            (self._tmpdir / filename + '.py').write_text(text, 'utf-8')


@pytest.fixture
def vultdir(tmpdir):
    return VultureDir(tmpdir)


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
    assert vultdir.run() == ["foo.py:2: Unused function 'foo'"]


def test_unused_var(vultdir):
    vultdir.makepyfile(foo="""
        foo = 42
    """)
    assert vultdir.run() == ["foo.py:2: Unused variable 'foo'"]


def test_unused_attr(vultdir):
    vultdir.makepyfile(foo="""
        class Foo():
            def __init__(self):
                self.foo = 42

        Foo()
    """)
    assert vultdir.run() == ["foo.py:4: Unused attribute 'foo'"]


def test_unused_prop(vultdir):
    vultdir.makepyfile(foo="""
        class Foo():

            @property
            def foo(self):
                return 42

        Foo()
    """)
    assert vultdir.run() == ["foo.py:4: Unused property 'foo'"]


def test_unused_method(vultdir):
    vultdir.makepyfile(foo="""
        class Foo():

            def foo(self):
                pass

        Foo()
    """)
    assert vultdir.run() == ["foo.py:4: Unused function 'foo'"]


def test_unused_method_camelcase(vultdir):
    """Should be ignored because those are Qt methods."""
    vultdir.makepyfile(foo="""
        class Foo():

            def fooBar(self):
                pass

        Foo()
    """)
    assert not vultdir.run()
