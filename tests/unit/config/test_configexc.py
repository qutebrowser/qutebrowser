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

"""Tests for qutebrowser.config.configexc."""

import textwrap

import pytest

from qutebrowser.config import configexc
from qutebrowser.utils import usertypes


def test_validation_error():
    e = configexc.ValidationError('val', 'msg')
    assert e.option is None
    assert str(e) == "Invalid value 'val' - msg"


@pytest.mark.parametrize('deleted, renamed, expected', [
    (False, None, "No option 'opt'"),
    (True, None, "No option 'opt' (this option was removed from qutebrowser)"),
    (False, 'new', "No option 'opt' (this option was renamed to 'new')"),
])
def test_no_option_error(deleted, renamed, expected):
    e = configexc.NoOptionError('opt', deleted=deleted, renamed=renamed)
    assert e.option == 'opt'
    assert str(e) == expected


def test_no_option_error_clash():
    with pytest.raises(AssertionError):
        configexc.NoOptionError('opt', deleted=True, renamed='foo')


def test_no_autoconfig_error():
    e = configexc.NoAutoconfigError('opt')
    expected = "The opt setting can only be set in config.py!"
    assert str(e) == expected


@pytest.mark.parametrize('raw_backends', [
    None,
    {'QtWebEngine': 'Qt 5.11', 'QtWebKit': False}
])
def test_backend_error(raw_backends):
    e = configexc.BackendError('foo', usertypes.Backend.QtWebKit, raw_backends)
    expected = "The foo setting is not available with the QtWebKit backend!"
    assert str(e) == expected


def test_backend_error_condition():
    e = configexc.BackendError('foo', usertypes.Backend.QtWebEngine,
                               {'QtWebEngine': 'Qt 5.11', 'QtWebKit': True})
    expected = "The foo setting needs Qt 5.11 with the QtWebEngine backend!"
    assert str(e) == expected


def test_no_pattern_error():
    e = configexc.NoPatternError('foo')
    expected = "The foo setting does not support URL patterns!"
    assert str(e) == expected


def test_desc_with_text():
    """Test ConfigErrorDesc.with_text."""
    old = configexc.ConfigErrorDesc("Error text", Exception("Exception text"))
    new = old.with_text("additional text")
    assert str(new) == 'Error text (additional text): Exception text'


@pytest.fixture
def errors():
    """Get a ConfigFileErrors object."""
    err1 = configexc.ConfigErrorDesc("Error text 1", Exception("Exception 1"))
    err2 = configexc.ConfigErrorDesc("Error text 2", Exception("Exception 2"),
                                     "Fake traceback")
    return configexc.ConfigFileErrors("config.py", [err1, err2])


def test_config_file_errors_str(errors):
    assert str(errors).splitlines() == [
        'Errors occurred while reading config.py:',
        '  Error text 1: Exception 1',
        '  Error text 2 - Exception: Exception 2',
    ]


def test_config_file_errors_html(errors):
    html = errors.to_html()
    assert textwrap.dedent(html) == textwrap.dedent("""
        Errors occurred while reading config.py:

        <ul>

            <li>
              <b>Error text 1</b>: Exception 1

            </li>

            <li>
              <b>Error text 2</b>: Exception 2

                <pre>
Fake traceback
                </pre>

            </li>

        </ul>
    """)
    # Make sure the traceback is not indented
    assert '<pre>\nFake traceback\n' in html


def test_config_file_errors_fatal():
    err = configexc.ConfigErrorDesc("Text", Exception("Text"))
    errors = configexc.ConfigFileErrors("state", [err], fatal=True)
    assert errors.fatal
