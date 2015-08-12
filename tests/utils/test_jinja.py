# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.jinja."""

import os.path

import pytest
import jinja2

from qutebrowser.utils import jinja


@pytest.fixture(autouse=True)
def patch_read_file(monkeypatch):
    """pytest fixture to patch utils.read_file."""
    def _read_file(path):
        """A read_file which returns a simple template if the path is right."""
        if path == os.path.join('html', 'test.html'):
            return """Hello {{var}}"""
        else:
            raise IOError("Invalid path {}!".format(path))

    monkeypatch.setattr('qutebrowser.utils.jinja.utils.read_file', _read_file)


def test_simple_template():
    """Test with a simple template."""
    template = jinja.env.get_template('test.html')
    # https://bitbucket.org/logilab/pylint/issue/490/
    data = template.render(var='World')  # pylint: disable=no-member
    assert data == "Hello World"


def test_not_found():
    """Test with a template which does not exist."""
    with pytest.raises(jinja2.TemplateNotFound) as excinfo:
        jinja.env.get_template('does_not_exist.html')
    assert str(excinfo.value) == 'does_not_exist.html'


def test_utf8():
    """Test rendering with an UTF8 template.

    This was an attempt to get a failing test case for #127 but it seems
    the issue is elsewhere.

    https://github.com/The-Compiler/qutebrowser/issues/127
    """
    template = jinja.env.get_template('test.html')
    # https://bitbucket.org/logilab/pylint/issue/490/
    data = template.render(var='\u2603')  # pylint: disable=no-member
    assert data == "Hello \u2603"


@pytest.mark.parametrize('name, expected', [
    (None, False),
    ('foo', False),
    ('foo.html', True),
    ('foo.htm', True),
    ('foo.xml', True),
    ('blah/bar/foo.html', True),
    ('foo.bar.html', True),
])
def test_autoescape(name, expected):
    assert jinja._guess_autoescape(name) == expected
