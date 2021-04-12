# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.utils.jinja."""

import pathlib
import logging

import jinja2.exceptions
import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.utils import jinja
from qutebrowser.config import configexc


@pytest.fixture(autouse=True)
def patch_read_file(monkeypatch):
    """pytest fixture to patch resources.read_file."""
    def _read_file(filepath):
        """A read_file which returns a simple template if the path is right."""
        path = pathlib.Path(filepath)
        html_path = pathlib.Path('html')
        if path == html_path / 'test.html':
            return """Hello {{var}}"""
        elif path == html_path / 'test2.html':
            return """{{ resource_url('utils/testfile') }}"""
        elif path == html_path / 'test3.html':
            return """{{ data_url('testfile.txt') }}"""
        elif path == html_path / 'undef.html':
            return """{{ does_not_exist() }}"""
        elif path == html_path / 'attributeerror.html':
            return """{{ obj.foobar }}"""
        else:
            raise OSError(f"Invalid path {filepath}!")

    def _read_file_binary(filepath):
        if filepath == 'testfile.txt':
            return b'foo'
        else:
            raise OSError(f"Invalid path {filepath}!")

    monkeypatch.setattr(jinja.resources, 'read_file', _read_file)
    monkeypatch.setattr(jinja.resources, 'read_file_binary', _read_file_binary)


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
    assert url.toDisplayString() == 'qute://resource/utils/testfile'


def test_data_url():
    """Test data_url() which can be used from templates."""
    data = jinja.render('test3.html')
    print(data)
    url = QUrl(data)
    assert url.isValid()
    assert data == 'data:text/plain;base64,Zm9v'  # 'foo'


def test_not_found(caplog):
    """Test with a template which does not exist."""
    with caplog.at_level(logging.ERROR):
        data = jinja.render('does_not_exist.html')
    assert "The does_not_exist.html template could not be found!" in data

    assert caplog.messages[0].startswith("The does_not_exist.html template"
                                         " could not be loaded from")


def test_utf8():
    """Test rendering with a UTF8 template.

    This was an attempt to get a failing test case for #127 but it seems
    the issue is elsewhere.

    https://github.com/qutebrowser/qutebrowser/issues/127
    """
    data = jinja.render('test.html', var='\u2603')
    assert data == "Hello \u2603"


def test_undefined_function(caplog):
    """Make sure undefined attributes crash since we preload resources.."""
    with pytest.raises(jinja2.exceptions.UndefinedError):
        jinja.render('undef.html')


def test_attribute_error():
    """Make sure accessing an unknown attribute fails."""
    with pytest.raises(AttributeError):
        jinja.render('attributeerror.html', obj=object())


@pytest.mark.parametrize('escape', [True, False])
def test_autoescape(escape):
    if not escape:
        with jinja.environment.no_autoescape():
            template = jinja.environment.from_string("{{ v }}")
        assert template.render(v='<foo') == '<foo'

    template = jinja.environment.from_string("{{ v }}")
    assert template.render(v='<foo') == '&lt;foo'


@pytest.mark.parametrize('template, expected', [
    ('{{ func1(conf.aliases) }} {{ func2(conf.backend) }}',
     ['aliases', 'backend']),
    ('{{ conf.aliases["a"].propname }}', ['aliases']),
    ('{{ conf.auto_save.interval + conf.hints.min_chars }}',
     ['auto_save.interval', 'hints.min_chars']),
    ('{{ notconf.a.b.c }}', []),
])
def test_template_config_variables(template, expected, config_stub):
    assert jinja.template_config_variables(template) == frozenset(expected)


@pytest.mark.parametrize('template', [
    '{{ func1(conf.aaa) }}',
    '{{ conf.bbb["a"].propname }}',
    '{{ conf.ccc + 1 }}',
])
def test_template_config_variables_no_option(template, config_stub):
    with pytest.raises(configexc.NoOptionError):
        jinja.template_config_variables(template)
