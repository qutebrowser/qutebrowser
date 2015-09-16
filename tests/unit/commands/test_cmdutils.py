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

"""Tests for qutebrowser.commands.cmdutils."""

import pytest

from qutebrowser.commands import cmdutils, cmdexc


class TestCheckOverflow:

    def test_good(self):
        cmdutils.check_overflow(1, 'int')

    def test_bad(self):
        int32_max = 2 ** 31 - 1

        with pytest.raises(cmdexc.CommandError) as excinfo:
            cmdutils.check_overflow(int32_max + 1, 'int')

        expected_str = ("Numeric argument is too large for internal int "
                        "representation.")

        assert str(excinfo.value) == expected_str


class TestArgOrCount:

    @pytest.mark.parametrize('arg, count', [(None, None), (1, 1)])
    def test_exceptions(self, arg, count):
        with pytest.raises(ValueError):
            cmdutils.arg_or_count(arg, count)

    @pytest.mark.parametrize('arg, count', [(1, None), (None, 1)])
    def test_normal(self, arg, count):
        assert cmdutils.arg_or_count(arg, count) == 1

    @pytest.mark.parametrize('arg, count, countzero, expected', [
        (0, None, 2, 0),
        (None, 0, 2, 2),
    ])
    def test_countzero(self, arg, count, countzero, expected):
        ret = cmdutils.arg_or_count(arg, count, countzero=countzero)
        assert ret == expected

    def test_default(self):
        assert cmdutils.arg_or_count(None, None, default=2) == 2


class TestCheckExclusive:

    @pytest.mark.parametrize('flags', [[], [False, True], [False, False]])
    def test_good(self, flags):
        cmdutils.check_exclusive(flags, [])

    def test_bad(self):
        with pytest.raises(cmdexc.CommandError) as excinfo:
            cmdutils.check_exclusive([True, True], 'xyz')

        assert str(excinfo.value) == "Only one of -x/-y/-z can be given!"



class TestRegister:

    # pylint: disable=unused-variable

    @pytest.fixture(autouse=True)
    def clear_globals(self, monkeypatch):
        """Clear the cmdutils globals between each test."""
        monkeypatch.setattr(cmdutils, 'cmd_dict', {})
        monkeypatch.setattr(cmdutils, 'aliases', [])

    def test_simple(self):
        @cmdutils.register()
        def fun():
            """Blah."""
            pass

        cmd = cmdutils.cmd_dict['fun']
        assert cmd.handler is fun
        assert cmd.name == 'fun'
        assert len(cmdutils.cmd_dict) == 1
        assert not cmdutils.aliases

    def test_underlines(self):
        """Make sure the function name is normalized correctly (_ -> -)."""
        @cmdutils.register()
        def eggs_bacon():
            """Blah."""
            pass

        assert cmdutils.cmd_dict['eggs-bacon'].name == 'eggs-bacon'
        assert 'eggs_bacon' not in cmdutils.cmd_dict

    def test_lowercasing(self):
        """Make sure the function name is normalized correctly (uppercase)."""
        @cmdutils.register()
        def Test():  # pylint: disable=invalid-name
            """Blah."""
            pass

        assert cmdutils.cmd_dict['test'].name == 'test'
        assert 'Test' not in cmdutils.cmd_dict

    def test_explicit_name(self):
        """Test register with explicit name."""
        @cmdutils.register(name='foobar')
        def fun():
            """Blah."""
            pass

        assert cmdutils.cmd_dict['foobar'].name == 'foobar'
        assert 'fun' not in cmdutils.cmd_dict
        assert len(cmdutils.cmd_dict) == 1
        assert not cmdutils.aliases

    def test_multiple_names(self):
        """Test register with name being a list."""
        @cmdutils.register(name=['foobar', 'blub'])
        def fun():
            """Blah."""
            pass

        assert cmdutils.cmd_dict['foobar'].name == 'foobar'
        assert cmdutils.cmd_dict['blub'].name == 'foobar'
        assert 'fun' not in cmdutils.cmd_dict
        assert len(cmdutils.cmd_dict) == 2
        assert cmdutils.aliases == ['blub']

    def test_multiple_registrations(self):
        """Make sure registering the same name twice raises ValueError."""
        @cmdutils.register(name=['foobar', 'blub'])
        def fun():
            """Blah."""
            pass

        with pytest.raises(ValueError):
            @cmdutils.register(name=['blah', 'blub'])
            def fun2():
                """Blah."""
                pass

    def test_instance(self):
        """Make sure the instance gets passed to Command."""
        @cmdutils.register(instance='foobar')
        def fun(self):
            """Blah."""
            pass
        assert cmdutils.cmd_dict['fun']._instance == 'foobar'

    def test_kwargs(self):
        """Make sure the other keyword arguments get passed to Command."""
        @cmdutils.register(hide=True)
        def fun():
            """Blah."""
            pass
        assert cmdutils.cmd_dict['fun'].hide
