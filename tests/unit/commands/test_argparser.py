# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.commands.argparser."""

import inspect
import enum

import pytest
from qutebrowser.qt.core import QUrl

from qutebrowser.commands import argparser, cmdexc


class Enum(enum.Enum):

    foo = enum.auto()
    foo_bar = enum.auto()


class TestArgumentParser:

    @pytest.fixture
    def parser(self):
        return argparser.ArgumentParser('foo')

    def test_name(self, parser):
        assert parser.name == 'foo'

    def test_exit(self, parser):
        parser.add_argument('--help', action='help')

        with pytest.raises(argparser.ArgumentParserExit) as excinfo:
            parser.parse_args(['--help'])

        assert excinfo.value.status == 0

    def test_error(self, parser):
        with pytest.raises(argparser.ArgumentParserError,
                           match="Unrecognized arguments: --foo"):
            parser.parse_args(['--foo'])

    def test_help(self, parser, tabbed_browser_stubs):
        parser.add_argument('--help', action=argparser.HelpAction, nargs=0)

        with pytest.raises(argparser.ArgumentParserExit):
            parser.parse_args(['--help'])

        expected_url = QUrl('qute://help/commands.html#foo')
        assert tabbed_browser_stubs[1].loaded_url == expected_url


@pytest.mark.parametrize('converter, typ, value, expected', [
    (argparser.multitype_conv, [Enum], 'foo', Enum.foo),
    (argparser.multitype_conv, [Enum], 'foo-bar', Enum.foo_bar),
    (argparser.multitype_conv, [int], '2', 2),
    (argparser.multitype_conv, [int, str], 'foo', 'foo'),
    (argparser.type_conv, Enum, 'foo', Enum.foo),
    (argparser.type_conv, Enum, 'foo-bar', Enum.foo_bar),
    (argparser.type_conv, int, '2', 2),
])
def test_type_conv_valid(converter, typ, value, expected):
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    assert converter(param, typ, value) == expected


@pytest.mark.parametrize('typ, value, type_message', [
    (Enum, 'blubb',
     'foo: Invalid value blubb - expected one of: foo, foo-bar'),
    (Enum, 'foo_bar',
     'foo: Invalid value foo_bar - expected one of: foo, foo-bar'),
    (int, '2.5', 'foo: Invalid int value 2.5'),
    (int, 'foo', 'foo: Invalid int value foo'),
])
@pytest.mark.parametrize('multi', [True, False])
def test_type_conv_invalid(typ, value, type_message, multi):
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    msg = {
        True: 'foo: Invalid value {}'.format(value),
        False: type_message,
    }[multi]
    converter, converter_type = {
        True: (argparser.multitype_conv, [typ]),
        False: (argparser.type_conv, typ),
    }[multi]

    with pytest.raises(cmdexc.ArgumentTypeError, match=msg):
        converter(param, converter_type, value)


def test_multitype_conv_invalid_type():
    """Test using an invalid type with a multitype converter."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(ValueError, match="foo: Unknown type None!"):
        argparser.multitype_conv(param, [None], '')


@pytest.mark.parametrize('value, typ', [(None, None), (42, int)])
def test_conv_default_param(value, typ):
    """The default value should always be a valid choice."""
    def func(foo=value):
        pass
    param = inspect.signature(func).parameters['foo']
    assert argparser.type_conv(param, typ, value, str_choices=['val']) == value


def test_conv_str_type():
    """Using a str literal as type used to mean exactly that's a valid value.

    This got replaced by @cmdutils.argument(..., choices=...), so we make sure
    no string annotations are there anymore.
    """
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(TypeError, match='foo: Legacy string type!'):
        argparser.type_conv(param, 'val', None)


def test_conv_str_choices_valid():
    """Calling str type with str_choices and valid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    converted = argparser.type_conv(param, str, 'val1',
                                    str_choices=['val1', 'val2'])
    assert converted == 'val1'


def test_conv_str_choices_invalid():
    """Calling str type with str_choices and invalid value."""
    param = inspect.Parameter('foo', inspect.Parameter.POSITIONAL_ONLY)
    with pytest.raises(cmdexc.ArgumentTypeError, match='foo: Invalid value '
                       'val3 - expected one of: val1, val2'):
        argparser.type_conv(param, str, 'val3', str_choices=['val1', 'val2'])
