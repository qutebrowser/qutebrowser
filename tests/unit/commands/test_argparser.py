# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


@pytest.mark.parametrize('types, value, valid', [
    (['foo'], 'foo', True),
    (['bar'], 'foo', False),
    (['foo', 'bar'], 'foo', True),
    (['foo', int], 'foo', True),
    (['bar', int], 'foo', False),

    ([Enum], Enum.foo, True),
    ([Enum], 'foo', True),
    ([Enum], 'foo-bar', True),
    ([Enum], 'foo_bar', True),
    ([Enum], 'blubb', False),

    ([int], 2, True),
    ([int], 2.5, True),
    ([int], '2', True),
    ([int], '2.5', False),
    ([int], 'foo', False),
    ([int], None, False),
    ([int, str], 'foo', True),
])
def test_multitype_conv(types, value, valid):
    converter = argparser.multitype_conv(types)

    if valid:
        converter(value)
    else:
        with pytest.raises(cmdexc.ArgumentTypeError) as excinfo:
            converter(value)
        assert str(excinfo.value) == 'Invalid value {}.'.format(value)


def test_multitype_conv_invalid_type():
    converter = argparser.multitype_conv([None])
    with pytest.raises(ValueError) as excinfo:
        converter('')
    assert str(excinfo.value) == "Unknown type None!"
