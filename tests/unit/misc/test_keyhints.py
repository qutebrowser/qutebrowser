# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

from collections import OrderedDict
import pytest

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
    config_stub.data = {
        'colors': {
            'keyhint.fg': 'white',
            'keyhint.fg.suffix': 'yellow',
            'keyhint.bg': 'black'
        },
        'fonts': {'keyhint': 'Comic Sans'},
        'ui': {'keyhint-blacklist': ''},
    }
    keyhint = KeyHintView(0, None)
    qtbot.add_widget(keyhint)
    assert keyhint.text() == ''
    return keyhint


def test_suggestions(keyhint, key_config_stub):
    """Test that keyhints are shown based on a prefix."""
    # we want the dict to return sorted items() for reliable testing
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('aa', 'cmd-aa'),
        ('ab', 'cmd-ab'),
        ('aba', 'cmd-aba'),
        ('abb', 'cmd-abb'),
        ('xd', 'cmd-xd'),
        ('xe', 'cmd-xe')]))

    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected_text(
        ('a', 'yellow', 'a', 'cmd-aa'),
        ('a', 'yellow', 'b', 'cmd-ab'),
        ('a', 'yellow', 'ba', 'cmd-aba'),
        ('a', 'yellow', 'bb', 'cmd-abb'))


def test_special_bindings(keyhint, key_config_stub):
    """Ensure a prefix of '<' doesn't suggest special keys."""
    # we want the dict to return sorted items() for reliable testing
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('<a', 'cmd-<a'),
        ('<b', 'cmd-<b'),
        ('<ctrl-a>', 'cmd-ctrla')]))

    keyhint.update_keyhint('normal', '<')
    assert keyhint.text() == expected_text(
        ('&lt;', 'yellow', 'a', 'cmd-&lt;a'),
        ('&lt;', 'yellow', 'b', 'cmd-&lt;b'))


def test_color_switch(keyhint, config_stub, key_config_stub):
    """Ensure the keyhint suffix color can be updated at runtime."""
    config_stub.set('colors', 'keyhint.fg.suffix', '#ABCDEF')
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('aa', 'cmd-aa')]))
    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected_text(('a', '#ABCDEF', 'a', 'cmd-aa'))


def test_no_matches(keyhint, key_config_stub):
    """Ensure the widget isn't visible if there are no keystrings to show."""
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('aa', 'cmd-aa'),
        ('ab', 'cmd-ab')]))
    keyhint.update_keyhint('normal', 'z')
    assert not keyhint.text()
    assert not keyhint.isVisible()


def test_blacklist(keyhint, config_stub, key_config_stub):
    """Test that blacklisted keychains aren't hinted."""
    config_stub.set('ui', 'keyhint-blacklist', ['ab*'])
    # we want the dict to return sorted items() for reliable testing
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('aa', 'cmd-aa'),
        ('ab', 'cmd-ab'),
        ('aba', 'cmd-aba'),
        ('abb', 'cmd-abb'),
        ('xd', 'cmd-xd'),
        ('xe', 'cmd-xe')]))

    keyhint.update_keyhint('normal', 'a')
    assert keyhint.text() == expected_text(('a', 'yellow', 'a', 'cmd-aa'))


def test_blacklist_all(keyhint, config_stub, key_config_stub):
    """Test that setting the blacklist to * disables keyhints."""
    config_stub.set('ui', 'keyhint-blacklist', ['*'])
    # we want the dict to return sorted items() for reliable testing
    key_config_stub.set_bindings_for('normal', OrderedDict([
        ('aa', 'cmd-aa'),
        ('ab', 'cmd-ab'),
        ('aba', 'cmd-aba'),
        ('abb', 'cmd-abb'),
        ('xd', 'cmd-xd'),
        ('xe', 'cmd-xe')]))

    keyhint.update_keyhint('normal', 'a')
    assert not keyhint.text()
