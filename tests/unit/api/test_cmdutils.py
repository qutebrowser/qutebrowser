# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=unused-variable

"""Tests for qutebrowser.api.cmdutils."""

import sys
import logging
import types
import typing
import enum

import pytest

from qutebrowser.misc import objects
from qutebrowser.commands import cmdexc, argparser, command
from qutebrowser.api import cmdutils
from qutebrowser.utils import usertypes


@pytest.fixture(autouse=True)
def clear_globals(monkeypatch):
    monkeypatch.setattr(objects, 'commands', {})


def _get_cmd(*args, **kwargs):
    """Get a command object created via @cmdutils.register.

    Args:
        Passed to @cmdutils.register decorator
    """
    @cmdutils.register(*args, **kwargs)
    def fun():
        """Blah."""
    return objects.commands['fun']


class TestCheckOverflow:

    def test_good(self):
        cmdutils.check_overflow(1, 'int')

    def test_bad(self):
        int32_max = 2 ** 31 - 1

        with pytest.raises(cmdutils.CommandError, match="Numeric argument is "
                           "too large for internal int representation."):
            cmdutils.check_overflow(int32_max + 1, 'int')


class TestCheckExclusive:

    @pytest.mark.parametrize('flags', [[], [False, True], [False, False]])
    def test_good(self, flags):
        cmdutils.check_exclusive(flags, [])

    def test_bad(self):
        with pytest.raises(cmdutils.CommandError,
                           match="Only one of -x/-y/-z can be given!"):
            cmdutils.check_exclusive([True, True], 'xyz')


class TestRegister:

    def test_simple(self):
        @cmdutils.register()
        def fun():
            """Blah."""

        cmd = objects.commands['fun']
        assert cmd.handler is fun
        assert cmd.name == 'fun'
        assert len(objects.commands) == 1

    def test_underlines(self):
        """Make sure the function name is normalized correctly (_ -> -)."""
        @cmdutils.register()
        def eggs_bacon():
            """Blah."""

        assert objects.commands['eggs-bacon'].name == 'eggs-bacon'
        assert 'eggs_bacon' not in objects.commands

    def test_lowercasing(self):
        """Make sure the function name is normalized correctly (uppercase)."""
        @cmdutils.register()
        def Test():  # noqa: N801,N806 pylint: disable=invalid-name
            """Blah."""

        assert objects.commands['test'].name == 'test'
        assert 'Test' not in objects.commands

    def test_explicit_name(self):
        """Test register with explicit name."""
        @cmdutils.register(name='foobar')
        def fun():
            """Blah."""

        assert objects.commands['foobar'].name == 'foobar'
        assert 'fun' not in objects.commands
        assert len(objects.commands) == 1

    def test_multiple_registrations(self):
        """Make sure registering the same name twice raises ValueError."""
        @cmdutils.register(name='foobar')
        def fun():
            """Blah."""

        with pytest.raises(ValueError):
            @cmdutils.register(name='foobar')
            def fun2():
                """Blah."""

    def test_instance(self):
        """Make sure the instance gets passed to Command."""
        @cmdutils.register(instance='foobar')
        def fun(self):
            """Blah."""
        assert objects.commands['fun']._instance == 'foobar'

    def test_star_args(self):
        """Check handling of *args."""
        @cmdutils.register()
        def fun(*args):
            """Blah."""
        with pytest.raises(argparser.ArgumentParserError):
            objects.commands['fun'].parser.parse_args([])

    def test_star_args_optional(self):
        """Check handling of *args withstar_args_optional."""
        @cmdutils.register(star_args_optional=True)
        def fun(*args):
            """Blah."""
            assert not args
        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args([])
        args, kwargs = cmd._get_call_args(win_id=0)
        fun(*args, **kwargs)

    def test_star_args_optional_annotated(self):
        @cmdutils.register(star_args_optional=True)
        def fun(*args: str):
            """Blah."""

        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args([])
        cmd._get_call_args(win_id=0)

    @pytest.mark.parametrize('inp, expected', [
        (['--arg'], True), (['-a'], True), ([], False)])
    def test_flag(self, inp, expected):
        @cmdutils.register()
        def fun(arg=False):
            """Blah."""
            assert arg == expected
        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args(inp)
        assert cmd.namespace.arg == expected

    def test_flag_argument(self):
        @cmdutils.register()
        @cmdutils.argument('arg', flag='b')
        def fun(arg=False):
            """Blah."""
            assert arg
        cmd = objects.commands['fun']

        with pytest.raises(argparser.ArgumentParserError):
            cmd.parser.parse_args(['-a'])

        cmd.namespace = cmd.parser.parse_args(['-b'])
        assert cmd.namespace.arg
        args, kwargs = cmd._get_call_args(win_id=0)
        fun(*args, **kwargs)

    def test_self_without_instance(self):
        with pytest.raises(TypeError, match="fun is a class method, but "
                           "instance was not given!"):
            @cmdutils.register()
            def fun(self):
                """Blah."""

    def test_instance_without_self(self):
        with pytest.raises(TypeError, match="fun is not a class method, but "
                           "instance was given!"):
            @cmdutils.register(instance='inst')
            def fun():
                """Blah."""

    def test_var_kw(self):
        with pytest.raises(TypeError, match="fun: functions with varkw "
                           "arguments are not supported!"):
            @cmdutils.register()
            def fun(**kwargs):
                """Blah."""

    def test_partial_arg(self):
        """Test with only some arguments decorated with @cmdutils.argument."""
        @cmdutils.register()
        @cmdutils.argument('arg1', flag='b')
        def fun(arg1=False, arg2=False):
            """Blah."""

    def test_win_id(self):
        @cmdutils.register()
        @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
        def fun(win_id):
            """Blah."""
        assert objects.commands['fun']._get_call_args(42) == ([42], {})

    def test_count(self):
        @cmdutils.register()
        @cmdutils.argument('count', value=cmdutils.Value.count)
        def fun(count=0):
            """Blah."""
        assert objects.commands['fun']._get_call_args(42) == ([0], {})

    def test_fill_self(self):
        with pytest.raises(TypeError, match="fun: Can't fill 'self' with "
                           "value!"):
            @cmdutils.register(instance='foobar')
            @cmdutils.argument('self', value=cmdutils.Value.count)
            def fun(self):
                """Blah."""

    def test_fill_invalid(self):
        with pytest.raises(TypeError, match="fun: Invalid value='foo' for "
                           "argument 'arg'!"):
            @cmdutils.register()
            @cmdutils.argument('arg', value='foo')
            def fun(arg):
                """Blah."""

    def test_count_without_default(self):
        with pytest.raises(TypeError, match="fun: handler has count parameter "
                           "without default!"):
            @cmdutils.register()
            @cmdutils.argument('count', value=cmdutils.Value.count)
            def fun(count):
                """Blah."""

    @pytest.mark.parametrize('hide', [True, False])
    def test_pos_args(self, hide):
        @cmdutils.register()
        @cmdutils.argument('arg', hide=hide)
        def fun(arg):
            """Blah."""

        pos_args = objects.commands['fun'].pos_args
        if hide:
            assert pos_args == []
        else:
            assert pos_args == [('arg', 'arg')]

    Enum = enum.Enum('Test', ['x', 'y'])

    @pytest.mark.parametrize('typ, inp, choices, expected', [
        (int, '42', None, 42),
        (int, 'x', None, cmdexc.ArgumentTypeError),
        (str, 'foo', None, 'foo'),

        (typing.Union[str, int], 'foo', None, 'foo'),
        (typing.Union[str, int], '42', None, 42),

        # Choices
        (str, 'foo', ['foo'], 'foo'),
        (str, 'bar', ['foo'], cmdexc.ArgumentTypeError),

        # Choices with Union: only checked when it's a str
        (typing.Union[str, int], 'foo', ['foo'], 'foo'),
        (typing.Union[str, int], 'bar', ['foo'], cmdexc.ArgumentTypeError),
        (typing.Union[str, int], '42', ['foo'], 42),

        (Enum, 'x', None, Enum.x),
        (Enum, 'z', None, cmdexc.ArgumentTypeError),
    ])
    def test_typed_args(self, typ, inp, choices, expected):
        @cmdutils.register()
        @cmdutils.argument('arg', choices=choices)
        def fun(arg: typ):
            """Blah."""
            assert arg == expected

        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args([inp])

        if expected is cmdexc.ArgumentTypeError:
            with pytest.raises(cmdexc.ArgumentTypeError):
                cmd._get_call_args(win_id=0)
        else:
            args, kwargs = cmd._get_call_args(win_id=0)
            assert args == [expected]
            assert kwargs == {}
            fun(*args, **kwargs)

    def test_choices_no_annotation(self):
        # https://github.com/qutebrowser/qutebrowser/issues/1871
        @cmdutils.register()
        @cmdutils.argument('arg', choices=['foo', 'bar'])
        def fun(arg):
            """Blah."""

        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args(['fish'])

        with pytest.raises(cmdexc.ArgumentTypeError):
            cmd._get_call_args(win_id=0)

    def test_choices_no_annotation_kwonly(self):
        # https://github.com/qutebrowser/qutebrowser/issues/1871
        @cmdutils.register()
        @cmdutils.argument('arg', choices=['foo', 'bar'])
        def fun(*, arg='foo'):
            """Blah."""

        cmd = objects.commands['fun']
        cmd.namespace = cmd.parser.parse_args(['--arg=fish'])

        with pytest.raises(cmdexc.ArgumentTypeError):
            cmd._get_call_args(win_id=0)

    def test_pos_arg_info(self):
        @cmdutils.register()
        @cmdutils.argument('foo', choices=('a', 'b'))
        @cmdutils.argument('bar', choices=('x', 'y'))
        @cmdutils.argument('opt')
        def fun(foo, bar, opt=False):
            """Blah."""

        cmd = objects.commands['fun']
        assert cmd.get_pos_arg_info(0) == command.ArgInfo(choices=('a', 'b'))
        assert cmd.get_pos_arg_info(1) == command.ArgInfo(choices=('x', 'y'))
        with pytest.raises(IndexError):
            cmd.get_pos_arg_info(2)

    def test_keyword_only_without_default(self):
        # https://github.com/qutebrowser/qutebrowser/issues/1872
        def fun(*, target):
            """Blah."""

        with pytest.raises(TypeError, match="fun: handler has keyword only "
                           "argument 'target' without default!"):
            fun = cmdutils.register()(fun)

    def test_typed_keyword_only_without_default(self):
        # https://github.com/qutebrowser/qutebrowser/issues/1872
        def fun(*, target: int):
            """Blah."""

        with pytest.raises(TypeError, match="fun: handler has keyword only "
                           "argument 'target' without default!"):
            fun = cmdutils.register()(fun)


class TestArgument:

    """Test the @cmdutils.argument decorator."""

    def test_invalid_argument(self):
        with pytest.raises(ValueError, match="fun has no argument foo!"):
            @cmdutils.argument('foo')
            def fun(bar):
                """Blah."""

    def test_storage(self):
        @cmdutils.argument('foo', flag='x')
        @cmdutils.argument('bar', flag='y')
        def fun(foo, bar):
            """Blah."""
        expected = {
            'foo': command.ArgInfo(flag='x'),
            'bar': command.ArgInfo(flag='y')
        }
        assert fun.qute_args == expected

    def test_arginfo_boolean(self):
        @cmdutils.argument('special1', value=cmdutils.Value.count)
        @cmdutils.argument('special2', value=cmdutils.Value.win_id)
        @cmdutils.argument('normal')
        def fun(special1, special2, normal):
            """Blah."""

        assert fun.qute_args['special1'].value
        assert fun.qute_args['special2'].value
        assert not fun.qute_args['normal'].value

    def test_wrong_order(self):
        """When @cmdutils.argument is used above (after) @register, fail."""
        with pytest.raises(ValueError, match=r"@cmdutils.argument got called "
                           r"above \(after\) @cmdutils.register for fun!"):
            @cmdutils.argument('bar', flag='y')
            @cmdutils.register()
            def fun(bar):
                """Blah."""

    def test_no_docstring(self, caplog):
        with caplog.at_level(logging.WARNING):
            @cmdutils.register()
            def fun():
                # no docstring
                pass

        assert len(caplog.records) == 1
        assert caplog.messages[0].endswith('test_cmdutils.py has no docstring')

    def test_no_docstring_with_optimize(self, monkeypatch):
        """With -OO we'd get a warning on start, but no warning afterwards."""
        monkeypatch.setattr(sys, 'flags', types.SimpleNamespace(optimize=2))

        @cmdutils.register()
        def fun():
            # no docstring
            pass


class TestRun:

    @pytest.fixture(autouse=True)
    def patch_backend(self, mode_manager, monkeypatch):
        monkeypatch.setattr(command.objects, 'backend',
                            usertypes.Backend.QtWebKit)

    @pytest.mark.parametrize('backend, used, ok', [
        (usertypes.Backend.QtWebEngine, usertypes.Backend.QtWebEngine, True),
        (usertypes.Backend.QtWebEngine, usertypes.Backend.QtWebKit, False),
        (usertypes.Backend.QtWebKit, usertypes.Backend.QtWebEngine, False),
        (usertypes.Backend.QtWebKit, usertypes.Backend.QtWebKit, True),
        (None, usertypes.Backend.QtWebEngine, True),
        (None, usertypes.Backend.QtWebKit, True),
    ])
    def test_backend(self, monkeypatch, backend, used, ok):
        monkeypatch.setattr(command.objects, 'backend', used)
        cmd = _get_cmd(backend=backend)
        if ok:
            cmd.run(win_id=0)
        else:
            with pytest.raises(cmdexc.PrerequisitesError,
                               match=r'.* backend\.'):
                cmd.run(win_id=0)

    def test_no_args(self):
        cmd = _get_cmd()
        cmd.run(win_id=0)

    def test_instance_unavailable_with_backend(self, monkeypatch):
        """Test what happens when a backend doesn't have an objreg object.

        For example, QtWebEngine doesn't have 'hintmanager' registered. We make
        sure the backend checking happens before resolving the instance, so we
        display an error instead of crashing.
        """
        @cmdutils.register(instance='doesnotexist',
                           backend=usertypes.Backend.QtWebEngine)
        def fun(self):
            """Blah."""

        monkeypatch.setattr(command.objects, 'backend',
                            usertypes.Backend.QtWebKit)
        cmd = objects.commands['fun']
        with pytest.raises(cmdexc.PrerequisitesError, match=r'.* backend\.'):
            cmd.run(win_id=0)
