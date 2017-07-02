# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.config."""

import copy

import pytest
from PyQt5.QtCore import QObject

from qutebrowser.config import config, configdata, configexc


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


class TestChangeFilter:

    @pytest.mark.parametrize('option', ['foobar', 'tab', 'tabss', 'tabs.'])
    def test_unknown_option(self, option):
        cf = config.change_filter(option)
        with pytest.raises(configexc.NoOptionError):
            cf.validate()

    @pytest.mark.parametrize('option', ['confirm_quit', 'tabs', 'tabs.show'])
    def test_validate(self, option):
        cf = config.change_filter(option)
        cf.validate()
        assert cf in config._change_filters

    @pytest.mark.parametrize('method', [True, False])
    @pytest.mark.parametrize('option, changed, matches', [
        ('confirm_quit', 'confirm_quit', True),
        ('tabs', 'tabs.show', True),
        ('tabs.show', 'tabs.show', True),
        ('tabs', None, True),
        ('tabs', 'colors.tabs.bar.bg', False),
    ])
    def test_call(self, method, option, changed, matches):
        was_called = False
        if method:

            class Foo:

                @config.change_filter(option)
                def meth(self):
                    nonlocal was_called
                    was_called = True

            foo = Foo()
            foo.meth(changed)

        else:

            @config.change_filter(option, function=True)
            def func():
                nonlocal was_called
                was_called = True

            func(changed)

        assert was_called == matches


class TestKeyConfig:

    @pytest.fixture
    def keyconf(self, config_stub):
        return config.KeyConfig(config_stub)

    @pytest.mark.parametrize('commands, expected', [
        # Unbinding default key
        ({'a': None}, {'b': 'bar'}),
        # Additional binding
        ({'c': 'baz'}, {'a': 'foo', 'b': 'bar', 'c': 'baz'}),
        # Unbinding unknown key
        ({'x': None}, {'a': 'foo', 'b': 'bar'}),
    ])
    def test_get_bindings_for(self, keyconf, config_stub, commands, expected):
        orig_default_bindings = {'normal': {'a': 'foo', 'b': 'bar'}}
        config_stub.val.bindings.default = copy.deepcopy(orig_default_bindings)
        config_stub.val.bindings.commands = {'normal': commands}
        bindings = keyconf.get_bindings_for('normal')

        # Make sure the code creates a copy and doesn't modify the setting
        assert config_stub.val.bindings.default == orig_default_bindings
        assert bindings == expected

    @pytest.mark.parametrize('bindings, expected', [
        # Simple
        ({'a': 'foo', 'b': 'bar'}, {'foo': ['a'], 'bar': ['b']}),
        # Multiple bindings
        ({'a': 'foo', 'b': 'foo'}, {'foo': ['b', 'a']}),
        # With special keys (should be listed last)
        ({'a': 'foo', '<Escape>': 'foo'}, {'foo': ['a', '<Escape>']}),
        # Chained command
        ({'a': 'foo ;; bar'}, {'foo': ['a'], 'bar': ['a']}),
    ])
    def test_get_reverse_bindings_for(self, keyconf, config_stub, bindings,
                                      expected):
        config_stub.val.bindings.default = {'normal': {}}
        config_stub.val.bindings.commands = {'normal': bindings}
        assert keyconf.get_reverse_bindings_for('normal') == expected

    @pytest.mark.parametrize('key, expected', [
        ('A', 'A'),
        ('<Ctrl-X>', '<ctrl+x>'),
    ])
    def test_prepare_valid(self, keyconf, key, expected):
        """Make sure prepare normalizes the key."""
        assert keyconf._prepare(key, 'normal') == expected

    def test_prepare_invalid(self, keyconf):
        """Make sure prepare checks the mode."""
        with pytest.raises(configexc.KeybindingError):
            assert keyconf._prepare('x', 'abnormal')


class StyleObj(QObject):

    def __init__(self, stylesheet=None, parent=None):
        super().__init__(parent)
        if stylesheet is not None:
            self.STYLESHEET = stylesheet  # pylint: disable=invalid-name
        self.rendered_stylesheet = None

    def setStyleSheet(self, stylesheet):
        self.rendered_stylesheet = stylesheet


def test_get_stylesheet(config_stub):
    config_stub.val.colors.completion.bg = 'magenta'
    observer = config.StyleSheetObserver(
        StyleObj(), stylesheet="{{ conf.colors.completion.bg }}")
    assert observer._get_stylesheet() == 'magenta'


@pytest.mark.parametrize('delete', [True, False])
@pytest.mark.parametrize('stylesheet_param', [True, False])
@pytest.mark.parametrize('update', [True, False])
def test_set_register_stylesheet(delete, stylesheet_param, update, qtbot,
                                 config_stub, caplog):
    config_stub.val.colors.completion.fg = 'magenta'
    stylesheet = "{{ conf.colors.completion.fg }}"

    with caplog.at_level(9):  # VDEBUG
        if stylesheet_param:
            obj = StyleObj()
            config.set_register_stylesheet(obj, stylesheet=stylesheet,
                                           update=update)
        else:
            obj = StyleObj(stylesheet)
            config.set_register_stylesheet(obj, update=update)

    assert len(caplog.records) == 1
    assert caplog.records[0].message == 'stylesheet for StyleObj: magenta'

    assert obj.rendered_stylesheet == 'magenta'

    if delete:
        with qtbot.waitSignal(obj.destroyed):
            obj.deleteLater()

    config_stub.val.colors.completion.fg = 'yellow'

    if delete or not update:
        expected = 'magenta'
    else:
        expected = 'yellow'

    assert obj.rendered_stylesheet == expected
