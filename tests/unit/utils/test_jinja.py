# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import os.path

import pytest
import logging
import jinja2
from PyQt5.QtCore import QUrl

from qutebrowser.utils import utils, jinja


@pytest.fixture(autouse=True)
def patch_read_file(monkeypatch):
    """pytest fixture to patch utils.read_file."""
    real_read_file = utils.read_file

    def _read_file(path):
        """A read_file which returns a simple template if the path is right."""
        if path == os.path.join('html', 'test.html'):
            return """Hello {{var}}"""
        elif path == os.path.join('html', 'test2.html'):
            return """{{ resource_url('utils/testfile') }}"""
        elif path == os.path.join('html', 'undef.html'):
            return """{{ does_not_exist() }}"""
        elif path == os.path.join('html', 'undef_error.html'):
            return real_read_file(path)
        else:
            raise IOError("Invalid path {}!".format(path))

    monkeypatch.setattr('qutebrowser.utils.jinja.utils.read_file', _read_file)


def test_simple_template():
    """Test with a simple template."""
    data = jinja.render('test.html', var='World')
    assert data == "Hello World"


def test_resource_url():
    """Test resource_url() which can be used from templates."""
    data = jinja.render('test2.html')
    print(data)
    url = QUrl(data)
    assert url.isValid()
    assert url.scheme() == 'file'

    path = url.path()

    if os.name == "nt":
        path = path.lstrip('/')
        path = path.replace('/', os.sep)

    with open(path, 'r', encoding='utf-8') as f:
        assert f.read().splitlines()[0] == "Hello World!"


def test_not_found():
    """Test with a template which does not exist."""
    with pytest.raises(jinja2.TemplateNotFound) as excinfo:
        jinja.render('does_not_exist.html')
    assert str(excinfo.value) == 'does_not_exist.html'


def test_utf8():
    """Test rendering with an UTF8 template.

    This was an attempt to get a failing test case for #127 but it seems
    the issue is elsewhere.

    https://github.com/The-Compiler/qutebrowser/issues/127
    """
    data = jinja.render('test.html', var='\u2603')
    assert data == "Hello \u2603"


def test_undefined_function(caplog):
    """Make sure we don't crash if an undefined function is called."""
    with caplog.at_level(logging.ERROR):
        data = jinja.render('undef.html')
    assert 'There was an error while rendering undef.html' in data
    assert "'does_not_exist' is undefined" in data
    assert data.startswith('<!DOCTYPE html>')

    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "UndefinedError while rendering undef.html"


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
