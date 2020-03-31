# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Test the keyhint widget."""

import pytest

from qutebrowser.misc import objects
from qutebrowser.misc.keyhintwidget import KeyHintView


def expected_text(*args):
    """Helper to format text we expect the KeyHintView to generate.

    Args:
        args: One tuple for each row in the expected output.
              Tuples are of the form: (prefix, color, suffix, command).
    """
    text = '<table>'
    for group in args:
        text += ("<tr>"
                 "<td>{}</td>"
                 "<td style='color: {}'>{}</td>"
                 "<td style='padding-left: 2ex'>{}</td>"
                 "</tr>").format(*group)

    return text + '</table>'


@pytest.fixture
def keyhint(qtbot, config_stub, key_config_stub):
    """Fixture to initialize a KeyHintView."""
    config_stub.val.colors.keyhint.suffix.fg = 'yellow'
    keyhint = KeyHintView(0, None)
    qtbot.add_widget(keyhint)
    assert keyhint.text() == ''
    return keyhint


def test_show_and_hide(qtbot, keyhint):
    with qtbot.waitSignal(keyhint.update_geometry):
        with qtbot.waitExposed(keyhint):
            keyhint.show()
    keyhint.update_keyhint('normal', '')
    assert not keyhint.isVisible()


def test_position_change(keyhint, config_stub):
    config_stub.val.statusbar.position = 'top'
    stylesheet = keyhint.styleSheet()
    assert 'border-bottom-right-radius' in stylesheet
    assert 'border-top-right-radius' not in stylesheet


def test_suggestions(keyhint, config_stub):
    """Test that keyhints are shown based on a prefix."""
    bindings = {'normal': {
        'aa': 'message-info cmd-aa',
        'ab': 'message-info cmd-ab',
        'aba': 'message-info cmd-aba',
        'abb': 'message-info cmd-abb',
        'xd': 'message-info cmd-xd',
        'xe': 'message-info cmd-xe',
    }}
    default_bindings = {'normal': {
        'ac': 'message-info cmd-ac',
    }}
    config_stub.val.bindings.default = default_bindings
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected_text(
        ('a', 'yellow', 'a', 'message-info cmd-aa'),
        ('a', 'yellow', 'b', 'message-info cmd-ab'),
        ('a', 'yellow', 'ba', 'message-info cmd-aba'),
        ('a', 'yellow', 'bb', 'message-info cmd-abb'),
        ('a', 'yellow', 'c', 'message-info cmd-ac'))


def test_suggestions_special(keyhint, config_stub):
    """Test that special characters work properly as prefix."""
    bindings = {'normal': {
        '<Ctrl-C>a': 'message-info cmd-Cca',
        '<Ctrl-C><Ctrl-C>': 'message-info cmd-CcCc',
        '<Ctrl-C><Ctrl-X>': 'message-info cmd-CcCx',
        'cbb': 'message-info cmd-cbb',
        'xd': 'message-info cmd-xd',
        'xe': 'message-info cmd-xe',
    }}
    default_bindings = {'normal': {
        '<Ctrl-C>c': 'message-info cmd-Ccc',
    }}
    config_stub.val.bindings.default = default_bindings
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', '<Ctrl+c>')
    assert keyhint.text() == expected_text(
        ('&lt;Ctrl+c&gt;', 'yellow', 'a', 'message-info cmd-Cca'),
        ('&lt;Ctrl+c&gt;', 'yellow', 'c', 'message-info cmd-Ccc'),
        ('&lt;Ctrl+c&gt;', 'yellow', '&lt;Ctrl+c&gt;',
         'message-info cmd-CcCc'),
        ('&lt;Ctrl+c&gt;', 'yellow', '&lt;Ctrl+x&gt;',
         'message-info cmd-CcCx'))


def test_suggestions_with_count(keyhint, config_stub, monkeypatch, stubs):
    """Test that a count prefix filters out commands that take no count."""
    monkeypatch.setattr(objects, 'commands', {
        'foo': stubs.FakeCommand(name='foo', takes_count=lambda: False),
        'bar': stubs.FakeCommand(name='bar', takes_count=lambda: True),
    })

    bindings = {'normal': {'aa': 'foo', 'ab': 'bar'}}
    config_stub.val.bindings.default = bindings
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', '2a')
    assert keyhint.text() == expected_text(
        ('a', 'yellow', 'b', 'bar'),
    )


def test_special_bindings(keyhint, config_stub):
    """Ensure a prefix of '<' doesn't suggest special keys."""
    bindings = {'normal': {
        '<a': 'message-info cmd-<a',
        '<b': 'message-info cmd-<b',
        '<ctrl-a>': 'message-info cmd-ctrla',
    }}
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', '<')

    assert keyhint.text() == expected_text(
        ('&lt;', 'yellow', 'a', 'message-info cmd-&lt;a'),
        ('&lt;', 'yellow', 'b', 'message-info cmd-&lt;b'))


def test_color_switch(keyhint, config_stub):
    """Ensure the keyhint suffix color can be updated at runtime."""
    bindings = {'normal': {'aa': 'message-info cmd-aa'}}
    config_stub.val.colors.keyhint.suffix.fg = '#ABCDEF'
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = bindings
    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected_text(('a', '#ABCDEF', 'a',
                                            'message-info cmd-aa'))


def test_no_matches(keyhint, config_stub):
    """Ensure the widget isn't visible if there are no keystrings to show."""
    bindings = {'normal': {
        'aa': 'message-info cmd-aa',
        'ab': 'message-info cmd-ab',
    }}
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', 'z')
    assert not keyhint.text()
    assert not keyhint.isVisible()


@pytest.mark.parametrize('blacklist, expected', [
    (['ab*'], expected_text(('a', 'yellow', 'a', 'message-info cmd-aa'))),
    (['*'], ''),
])
def test_blacklist(keyhint, config_stub, blacklist, expected):
    """Test that blacklisted keychains aren't hinted."""
    config_stub.val.keyhint.blacklist = blacklist
    bindings = {'normal': {
        'aa': 'message-info cmd-aa',
        'ab': 'message-info cmd-ab',
        'aba': 'message-info cmd-aba',
        'abb': 'message-info cmd-abb',
        'xd': 'message-info cmd-xd',
        'xe': 'message-info cmd-xe',
    }}
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = bindings

    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected


def test_delay(qtbot, stubs, monkeypatch, config_stub, key_config_stub):
    timer = stubs.FakeTimer()
    monkeypatch.setattr(
        'qutebrowser.misc.keyhintwidget.usertypes.Timer',
        lambda *_: timer)
    interval = 200

    bindings = {'normal': {'aa': 'message-info cmd-aa'}}
    config_stub.val.keyhint.delay = interval
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = bindings

    keyhint = KeyHintView(0, None)
    keyhint.update_keyhint('normal', 'a')
    assert timer.isSingleShot()
    assert timer.interval() == interval
