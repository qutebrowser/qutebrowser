# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest
from PyQt5.QtCore import Qt

from tests.unit.keyinput import key_data
from qutebrowser.utils import utils
from qutebrowser.keyinput import keyutils


@pytest.fixture(params=key_data.KEYS, ids=lambda k: k.attribute)
def qt_key(request):
    key = request.param
    member = getattr(Qt, 'Key_' + key.attribute, None)
    if member is None:
        pytest.skip("Did not find key {}".format(key.attribute))
    key.member = member
    return key


@pytest.mark.parametrize('upper', [False, True])
def test_key_text(qt_key, upper):
    modifiers = Qt.ShiftModifier if upper else Qt.KeyboardModifiers()
    info = keyutils.KeyInfo(qt_key.member, modifiers=modifiers)
    expected = qt_key.uppertext if upper else qt_key.text
    assert info.text() == expected


class TestKeyToString:

    def test_to_string(self, qt_key):
        name = qt_key.attribute if qt_key.name is None else qt_key.name
        assert keyutils._key_to_string(qt_key.member) == name

    def test_missing(self, monkeypatch):
        monkeypatch.delattr(keyutils.Qt, 'Key_Blue')
        # We don't want to test the key which is actually missing - we only
        # want to know if the mapping still behaves properly.
        assert keyutils._key_to_string(Qt.Key_A) == 'A'

    def test_all(self):
        """Make sure all possible keys are in key_data.KEYS."""
        key_names = {name[len("Key_"):]
                     for name, value in sorted(vars(Qt).items())
                     if isinstance(value, Qt.Key)}
        key_data_names = {key.attribute for key in sorted(key_data.KEYS)}
        diff = key_names - key_data_names
        assert not diff


class TestKeyEventToString:

    """Test keyevent_to_string."""

    def test_only_control(self, fake_keyevent_factory):
        """Test keyeevent when only control is pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_Control,
                                    modifiers=Qt.ControlModifier)
        assert not str(keyutils.KeyInfo.from_event(evt))

    def test_only_hyper_l(self, fake_keyevent_factory):
        """Test keyeevent when only Hyper_L is pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_Hyper_L,
                                    modifiers=Qt.MetaModifier)
        assert not str(keyutils.KeyInfo.from_event(evt))

    def test_only_key(self, fake_keyevent_factory):
        """Test with a simple key pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_A)
        assert str(keyutils.KeyInfo.from_event(evt)) == 'a'

    def test_key_and_modifier(self, fake_keyevent_factory):
        """Test with key and modifier pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        expected = '<Meta+a>' if utils.is_mac else '<Ctrl+a>'
        assert str(keyutils.KeyInfo.from_event(evt)) == expected

    def test_key_and_modifiers(self, fake_keyevent_factory):
        """Test with key and multiple modifiers pressed."""
        evt = fake_keyevent_factory(
            key=Qt.Key_A, modifiers=(Qt.ControlModifier | Qt.AltModifier |
                                     Qt.MetaModifier | Qt.ShiftModifier))
        s = str(keyutils.KeyInfo.from_event(evt))
        assert s == '<Ctrl+Alt+Meta+Shift+a>'

    @pytest.mark.fake_os('mac')
    def test_mac(self, fake_keyevent_factory):
        """Test with a simulated mac."""
        evt = fake_keyevent_factory(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        assert str(keyutils.KeyInfo.from_event(evt)) == '<Meta+a>'


@pytest.mark.parametrize('keystr, expected', [
    ('<Control-x>', keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X)),
    ('<Meta-x>', keyutils.KeySequence(Qt.MetaModifier | Qt.Key_X)),
    ('<Ctrl-Alt-y>',
     keyutils.KeySequence(Qt.ControlModifier | Qt.AltModifier | Qt.Key_Y)),
    ('x', keyutils.KeySequence(Qt.Key_X)),
    ('X', keyutils.KeySequence(Qt.ShiftModifier | Qt.Key_X)),
    ('<Escape>', keyutils.KeySequence(Qt.Key_Escape)),
    ('xyz', keyutils.KeySequence(Qt.Key_X, Qt.Key_Y, Qt.Key_Z)),
    ('<Control-x><Meta-y>', keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X,
                                                 Qt.MetaModifier | Qt.Key_Y)),
    ('<blub>', keyutils.KeyParseError),
    ('\U00010000', keyutils.KeyParseError),
])
def test_parse(keystr, expected):
    if expected is keyutils.KeyParseError:
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence.parse(keystr)
    else:
        assert keyutils.KeySequence.parse(keystr) == expected


@pytest.mark.parametrize('orig, normalized', [
    ('<Control+x>', '<ctrl+x>'),
    ('<Windows+x>', '<meta+x>'),
    ('<Mod1+x>', '<alt+x>'),
    ('<Mod4+x>', '<meta+x>'),
    ('<Control-->', '<ctrl+->'),
    ('<Windows++>', '<meta++>'),
    ('<ctrl-x>', '<ctrl+x>'),
    ('<control+x>', '<ctrl+x>')
])
def test_normalize_keystr(orig, normalized):
    expected = keyutils.KeySequence.parse(normalized)
    assert keyutils.KeySequence.parse(orig) == expected
