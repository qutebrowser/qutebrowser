# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.commands.argparser."""

import inspect

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.commands import argparser, cmdexc
from qutebrowser.utils import usertypes, objreg


Enum = usertypes.enum('Enum', ['foo', 'foo_bar'])


class FakeTabbedBrowser:

    def __init__(self):
        self.opened_url = None

    def tabopen(self, url):
        self.opened_url = url


class TestArgumentParser:

    @pytest.fixture
    def parser(self):
        return argparser.ArgumentParser('foo')

    @pytest.yield_fixture
    def tabbed_browser(self, win_registry):
        tb = FakeTabbedBrowser()
        objreg.register('tabbed-browser', tb, scope='window', window=0)
        yield tb
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_name(self, parser):
        assert parser.name == 'foo'

    def test_exit(self, parser):
        parser.add_argument('--help', action='help')

        with pytest.raises(argparser.ArgumentParserExit) as excinfo:
            parser.parse_args(['--help'])

        assert excinfo.value.status == 0

    def test_error(self, parser):
        with pytest.raises(argparser.ArgumentParserError) as excinfo:
            parser.parse_args(['--foo'])
        assert str(excinfo.value) == "Unrecognized arguments: --foo"

    def test_help(self, parser, tabbed_browser):
        parser.add_argument('--help', action=argparser.HelpAction, nargs=0)

        with pytest.raises(argparser.ArgumentParserExit):
            parser.parse_args(['--help'])

        expected_url = QUrl('qute://help/commands.html#foo')
        assert tabbed_browser.opened_url == expected_url


@pytest.mark.parametrize('types, value, expected', [
    # expected: None to say it's an invalid value
    ([Enum], Enum.foo, Enum.foo),
    ([Enum], 'foo', Enum.foo),
    ([Enum], 'foo-bar', Enum.foo_bar),
    ([Enum], 'blubb', None),
    ([Enum], 'foo_bar', None),

    ([int], 2, 2),
    ([int], '2', 2),
    ([int], '2.5', None),
    ([int], 'foo', None),
    ([int, str], 'foo', 'foo'),
    ([str, int], '23', 23),
])
@pytest.mark.parametrize('multi', [True, False])
def test_type_conv(types, value, expected, multi):
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)

    if multi:
        converter = argparser.multitype_conv(param, types)
    elif len(types) == 1:
        converter = argparser.type_conv(param, types[0])
    else:
        return

    if expected is not None:
        assert converter(value) == expected
    else:
        with pytest.raises(cmdexc.ArgumentTypeError) as excinfo:
            converter(value)

        if multi:
            msg = 'foo: Invalid value {}'.format(value)
        elif types[0] is Enum:
            msg = ('foo: Invalid value {} - expected one of: foo, '
                   'foo-bar'.format(value))
        else:
            msg = 'foo: Invalid {} value {}'.format(types[0].__name__, value)
        assert str(excinfo.value) == msg


def test_multitype_conv_invalid_type():
    """Test using an invalid type with a multitype converter."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    converter = argparser.multitype_conv(param, [None])
    with pytest.raises(ValueError) as excinfo:
        converter('')
    assert str(excinfo.value) == "foo: Unknown type None!"


def test_conv_default_param():
    """The default value should always be a valid choice."""
    def func(foo=None):
        pass
    param = inspect.signature(func).parameters['foo']
    converter = argparser.type_conv(param, str, str_choices=['val'])
    assert converter(None) is None


def test_conv_str_type():
    """Using a str literal as type used to mean exactly that's a valid value.

    This got replaced by @cmdutils.argument(..., choices=...), so we make sure
    no string annotations are there anymore.
    """
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(TypeError) as excinfo:
        argparser.type_conv(param, 'val')
    assert str(excinfo.value) == 'foo: Legacy string type!'


def test_conv_str_choices_valid():
    """Calling str type with str_choices and valid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    converter = argparser.type_conv(param, str, str_choices=['val1', 'val2'])
    assert converter('val1') == 'val1'


def test_conv_str_choices_invalid():
    """Calling str type with str_choices and invalid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    converter = argparser.type_conv(param, str, str_choices=['val1', 'val2'])
    with pytest.raises(cmdexc.ArgumentTypeError) as excinfo:
        converter('val3')
    msg = 'foo: Invalid value val3 - expected one of: val1, val2'
    assert str(excinfo.value) == msg
