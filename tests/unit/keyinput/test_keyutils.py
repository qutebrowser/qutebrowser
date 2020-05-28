# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import operator

import hypothesis
from hypothesis import strategies
import pytest
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QKeySequence
from PyQt5.QtWidgets import QWidget

from unit.keyinput import key_data
from qutebrowser.keyinput import keyutils
from qutebrowser.utils import utils


@pytest.fixture(params=key_data.KEYS, ids=lambda k: k.attribute)
def qt_key(request):
    """Get all existing keys from key_data.py.

    Keys which don't exist with this Qt version result in skipped tests.
    """
    key = request.param
    if key.member is None:
        pytest.skip("Did not find key {}".format(key.attribute))
    return key


@pytest.fixture(params=key_data.MODIFIERS, ids=lambda m: m.attribute)
def qt_mod(request):
    """Get all existing modifiers from key_data.py."""
    mod = request.param
    assert mod.member is not None
    return mod


@pytest.fixture(params=[key for key in key_data.KEYS if key.qtest],
                ids=lambda k: k.attribute)
def qtest_key(request):
    """Get keys from key_data.py which can be used with QTest."""
    return request.param


def test_key_data_keys():
    """Make sure all possible keys are in key_data.KEYS."""
    key_names = {name[len("Key_"):]
                 for name, value in sorted(vars(Qt).items())
                 if isinstance(value, Qt.Key)}
    key_data_names = {key.attribute for key in sorted(key_data.KEYS)}
    diff = key_names - key_data_names
    assert not diff


def test_key_data_modifiers():
    """Make sure all possible modifiers are in key_data.MODIFIERS."""
    mod_names = {name[:-len("Modifier")]
                 for name, value in sorted(vars(Qt).items())
                 if isinstance(value, Qt.KeyboardModifier) and
                 value not in [Qt.NoModifier, Qt.KeyboardModifierMask]}
    mod_data_names = {mod.attribute for mod in sorted(key_data.MODIFIERS)}
    diff = mod_names - mod_data_names
    assert not diff


class KeyTesterWidget(QWidget):

    """Widget to get the text of QKeyPressEvents.

    This is done so we can check QTest::keyToAscii (qasciikey.cpp) as we can't
    call that directly, only via QTest::keyPress.
    """

    got_text = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = None

    def keyPressEvent(self, e):
        self.text = e.text()
        self.got_text.emit()


class TestKeyInfoText:

    @pytest.mark.parametrize('upper', [False, True])
    def test_text(self, qt_key, upper):
        """Test KeyInfo.text() with all possible keys.

        See key_data.py for inputs and expected values.
        """
        modifiers = Qt.ShiftModifier if upper else Qt.KeyboardModifiers()
        info = keyutils.KeyInfo(qt_key.member, modifiers=modifiers)
        expected = qt_key.uppertext if upper else qt_key.text
        assert info.text() == expected

    @pytest.fixture
    def key_tester(self, qtbot):
        w = KeyTesterWidget()
        qtbot.add_widget(w)
        return w

    def test_text_qtest(self, qtest_key, qtbot, key_tester):
        """Make sure KeyInfo.text() lines up with QTest::keyToAscii.

        See key_data.py for inputs and expected values.
        """
        with qtbot.wait_signal(key_tester.got_text):
            qtbot.keyPress(key_tester, qtest_key.member)

        info = keyutils.KeyInfo(qtest_key.member,
                                modifiers=Qt.KeyboardModifiers())
        assert info.text() == key_tester.text.lower()


class TestKeyToString:

    def test_to_string(self, qt_key):
        assert keyutils._key_to_string(qt_key.member) == qt_key.name

    def test_modifiers_to_string(self, qt_mod):
        expected = qt_mod.name + '+'
        assert keyutils._modifiers_to_string(qt_mod.member) == expected

    def test_missing(self, monkeypatch):
        monkeypatch.delattr(keyutils.Qt, 'Key_AltGr')
        # We don't want to test the key which is actually missing - we only
        # want to know if the mapping still behaves properly.
        assert keyutils._key_to_string(Qt.Key_A) == 'A'


@pytest.mark.parametrize('key, modifiers, expected', [
    (Qt.Key_A, Qt.NoModifier, 'a'),
    (Qt.Key_A, Qt.ShiftModifier, 'A'),

    (Qt.Key_Space, Qt.NoModifier, '<Space>'),
    (Qt.Key_Space, Qt.ShiftModifier, '<Shift+Space>'),
    (Qt.Key_Tab, Qt.ShiftModifier, '<Shift+Tab>'),
    (Qt.Key_A, Qt.ControlModifier, '<Ctrl+a>'),
    (Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier, '<Ctrl+Shift+a>'),
    (Qt.Key_A,
     Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier | Qt.ShiftModifier,
     '<Meta+Ctrl+Alt+Shift+a>'),
    (ord('Œ'), Qt.NoModifier, '<Œ>'),
    (ord('Œ'), Qt.ShiftModifier, '<Shift+Œ>'),
    (ord('Œ'), Qt.GroupSwitchModifier, '<AltGr+Œ>'),
    (ord('Œ'), Qt.GroupSwitchModifier | Qt.ShiftModifier, '<AltGr+Shift+Œ>'),

    (Qt.Key_Shift, Qt.ShiftModifier, '<Shift>'),
    (Qt.Key_Shift, Qt.ShiftModifier | Qt.ControlModifier, '<Ctrl+Shift>'),
    (Qt.Key_Alt, Qt.AltModifier, '<Alt>'),
    (Qt.Key_Shift, Qt.GroupSwitchModifier | Qt.ShiftModifier, '<AltGr+Shift>'),
    (Qt.Key_AltGr, Qt.GroupSwitchModifier, '<AltGr>'),
])
def test_key_info_str(key, modifiers, expected):
    assert str(keyutils.KeyInfo(key, modifiers)) == expected


@pytest.mark.parametrize('info1, info2, equal', [
    (keyutils.KeyInfo(Qt.Key_A, Qt.NoModifier),
     keyutils.KeyInfo(Qt.Key_A, Qt.NoModifier),
     True),
    (keyutils.KeyInfo(Qt.Key_A, Qt.NoModifier),
     keyutils.KeyInfo(Qt.Key_B, Qt.NoModifier),
     False),
    (keyutils.KeyInfo(Qt.Key_A, Qt.NoModifier),
     keyutils.KeyInfo(Qt.Key_B, Qt.ControlModifier),
     False),
])
def test_hash(info1, info2, equal):
    assert (hash(info1) == hash(info2)) == equal


@pytest.mark.parametrize('key, modifiers, text, expected', [
    (0xd83c, Qt.NoModifier, '🏻', '<🏻>'),
    (0xd867, Qt.NoModifier, '𩷶', '<𩷶>'),
    (0xd867, Qt.ShiftModifier, '𩷶', '<Shift+𩷶>'),
])
def test_surrogates(key, modifiers, text, expected):
    evt = QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)
    assert str(keyutils.KeyInfo.from_event(evt)) == expected


@pytest.mark.parametrize('keys, expected', [
    ([0x1f3fb], '<🏻>'),
    ([0x29df6], '<𩷶>'),
    ([Qt.Key_Shift, 0x29df6], '<Shift><𩷶>'),
    ([0x1f468, 0x200d, 0x1f468, 0x200d, 0x1f466], '<👨><‍><👨><‍><👦>'),
])
def test_surrogate_sequences(keys, expected):
    seq = keyutils.KeySequence(*keys)
    assert str(seq) == expected


# This shouldn't happen, but if it does we should handle it well
def test_surrogate_error():
    evt = QKeyEvent(QKeyEvent.KeyPress, 0xd83e, Qt.NoModifier, '🤞🏻')
    with pytest.raises(keyutils.KeyParseError):
        keyutils.KeyInfo.from_event(evt)


@pytest.mark.parametrize('keystr, expected', [
    ('foo', "Could not parse 'foo': error"),
    (None, "Could not parse keystring: error"),
])
def test_key_parse_error(keystr, expected):
    exc = keyutils.KeyParseError(keystr, "error")
    assert str(exc) == expected


@pytest.mark.parametrize('keystr, parts', [
    ('a', ['a']),
    ('ab', ['a', 'b']),
    ('a<', ['a', '<']),
    ('a>', ['a', '>']),
    ('<a', ['<', 'a']),
    ('>a', ['>', 'a']),
    ('aA', ['a', 'Shift+A']),
    ('a<Ctrl+a>b', ['a', 'ctrl+a', 'b']),
    ('<Ctrl+a>a', ['ctrl+a', 'a']),
    ('a<Ctrl+a>', ['a', 'ctrl+a']),
    ('<Ctrl-a>', ['ctrl+a']),
    ('<Num-a>', ['num+a']),
])
def test_parse_keystr(keystr, parts):
    assert list(keyutils._parse_keystring(keystr)) == parts


class TestKeySequence:

    def test_init(self):
        seq = keyutils.KeySequence(Qt.Key_A, Qt.Key_B, Qt.Key_C, Qt.Key_D,
                                   Qt.Key_E)
        assert len(seq._sequences) == 2
        assert len(seq._sequences[0]) == 4
        assert len(seq._sequences[1]) == 1

    def test_init_empty(self):
        seq = keyutils.KeySequence()
        assert not seq

    @pytest.mark.parametrize('key', [Qt.Key_unknown, -1, 0])
    def test_init_unknown(self, key):
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence(key)

    def test_parse_unknown(self):
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence.parse('\x1f')

    @pytest.mark.parametrize('orig, normalized', [
        ('<Control+x>', '<Ctrl+x>'),
        ('<Windows+x>', '<Meta+x>'),
        ('<Mod4+x>', '<Meta+x>'),
        ('<Command+x>', '<Meta+x>'),
        ('<Cmd+x>', '<Meta+x>'),
        ('<Mod1+x>', '<Alt+x>'),
        ('<Control-->', '<Ctrl+->'),
        ('<Windows++>', '<Meta++>'),
        ('<ctrl-x>', '<Ctrl+x>'),
        ('<control+x>', '<Ctrl+x>'),
        ('<a>b', 'ab'),
    ])
    def test_str_normalization(self, orig, normalized):
        assert str(keyutils.KeySequence.parse(orig)) == normalized

    def test_iter(self):
        seq = keyutils.KeySequence(Qt.Key_A | Qt.ControlModifier,
                                   Qt.Key_B | Qt.ShiftModifier,
                                   Qt.Key_C,
                                   Qt.Key_D,
                                   Qt.Key_E)
        expected = [keyutils.KeyInfo(Qt.Key_A, Qt.ControlModifier),
                    keyutils.KeyInfo(Qt.Key_B, Qt.ShiftModifier),
                    keyutils.KeyInfo(Qt.Key_C, Qt.NoModifier),
                    keyutils.KeyInfo(Qt.Key_D, Qt.NoModifier),
                    keyutils.KeyInfo(Qt.Key_E, Qt.NoModifier)]
        assert list(seq) == expected

    def test_repr(self):
        seq = keyutils.KeySequence(Qt.Key_A | Qt.ControlModifier,
                                   Qt.Key_B | Qt.ShiftModifier)
        assert repr(seq) == ("<qutebrowser.keyinput.keyutils.KeySequence "
                             "keys='<Ctrl+a>B'>")

    @pytest.mark.parametrize('sequences, expected', [
        (['a', ''], ['', 'a']),
        (['abcdf', 'abcd', 'abcde'], ['abcd', 'abcde', 'abcdf']),
    ])
    def test_sorting(self, sequences, expected):
        result = sorted(keyutils.KeySequence.parse(seq) for seq in sequences)
        expected_result = [keyutils.KeySequence.parse(seq) for seq in expected]
        assert result == expected_result

    @pytest.mark.parametrize('seq1, seq2, op, result', [
        ('a', 'a', operator.eq, True),
        ('a', '<a>', operator.eq, True),
        ('a', '<Shift-a>', operator.eq, False),
        ('a', 'b', operator.lt, True),
        ('a', 'b', operator.le, True),
    ])
    def test_operators(self, seq1, seq2, op, result):
        seq1 = keyutils.KeySequence.parse(seq1)
        seq2 = keyutils.KeySequence.parse(seq2)
        assert op(seq1, seq2) == result

        opposite = {
            operator.lt: operator.ge,
            operator.gt: operator.le,
            operator.le: operator.gt,
            operator.ge: operator.lt,
            operator.eq: operator.ne,
            operator.ne: operator.eq,
        }
        assert opposite[op](seq1, seq2) != result

    @pytest.mark.parametrize('op, result', [
        (operator.eq, False),
        (operator.ne, True),
    ])
    def test_operators_other_type(self, op, result):
        seq = keyutils.KeySequence.parse('a')
        assert op(seq, 'x') == result

    @pytest.mark.parametrize('seq1, seq2, equal', [
        ('a', 'a', True),
        ('a', 'A', False),
        ('a', '<a>', True),
        ('abcd', 'abcde', False),
    ])
    def test_hash(self, seq1, seq2, equal):
        seq1 = keyutils.KeySequence.parse(seq1)
        seq2 = keyutils.KeySequence.parse(seq2)
        assert (hash(seq1) == hash(seq2)) == equal

    @pytest.mark.parametrize('seq, length', [
        ('', 0),
        ('a', 1),
        ('A', 1),
        ('<Ctrl-a>', 1),
        ('abcde', 5)
    ])
    def test_len(self, seq, length):
        assert len(keyutils.KeySequence.parse(seq)) == length

    def test_bool(self):
        seq1 = keyutils.KeySequence.parse('abcd')
        seq2 = keyutils.KeySequence()
        assert seq1
        assert not seq2

    def test_getitem(self):
        seq = keyutils.KeySequence.parse('ab')
        expected = keyutils.KeyInfo(Qt.Key_B, Qt.NoModifier)
        assert seq[1] == expected

    def test_getitem_slice(self):
        s1 = 'abcdef'
        s2 = 'de'
        seq = keyutils.KeySequence.parse(s1)
        expected = keyutils.KeySequence.parse(s2)
        assert s1[3:5] == s2
        assert seq[3:5] == expected

    MATCH_TESTS = [
        # config: abcd
        ('abc', 'abcd', QKeySequence.PartialMatch),
        ('abcd', 'abcd', QKeySequence.ExactMatch),
        ('ax', 'abcd', QKeySequence.NoMatch),
        ('abcdef', 'abcd', QKeySequence.NoMatch),

        # config: abcd ef
        ('abc', 'abcdef', QKeySequence.PartialMatch),
        ('abcde', 'abcdef', QKeySequence.PartialMatch),
        ('abcd', 'abcdef', QKeySequence.PartialMatch),
        ('abcdx', 'abcdef', QKeySequence.NoMatch),
        ('ax', 'abcdef', QKeySequence.NoMatch),
        ('abcdefg', 'abcdef', QKeySequence.NoMatch),
        ('abcdef', 'abcdef', QKeySequence.ExactMatch),

        # other examples
        ('ab', 'a', QKeySequence.NoMatch),

        # empty strings
        ('', '', QKeySequence.ExactMatch),
        ('', 'a', QKeySequence.PartialMatch),
        ('a', '', QKeySequence.NoMatch)]

    @pytest.mark.parametrize('entered, configured, match_type', MATCH_TESTS)
    def test_matches(self, entered, configured, match_type):
        entered = keyutils.KeySequence.parse(entered)
        configured = keyutils.KeySequence.parse(configured)
        assert entered.matches(configured) == match_type

    @pytest.mark.parametrize('old, key, modifiers, text, expected', [
        ('a', Qt.Key_B, Qt.NoModifier, 'b', 'ab'),
        ('a', Qt.Key_B, Qt.ShiftModifier, 'B', 'aB'),
        ('a', Qt.Key_B, Qt.AltModifier | Qt.ShiftModifier, 'B',
         'a<Alt+Shift+b>'),

        # Modifier stripping with symbols
        ('', Qt.Key_Colon, Qt.NoModifier, ':', ':'),
        ('', Qt.Key_Colon, Qt.ShiftModifier, ':', ':'),
        ('', Qt.Key_Colon, Qt.AltModifier | Qt.ShiftModifier, ':',
         '<Alt+Shift+:>'),

        # Swapping Control/Meta on macOS
        ('', Qt.Key_A, Qt.ControlModifier, '',
         '<Meta+A>' if utils.is_mac else '<Ctrl+A>'),
        ('', Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier, '',
         '<Meta+Shift+A>' if utils.is_mac else '<Ctrl+Shift+A>'),
        ('', Qt.Key_A, Qt.MetaModifier, '',
         '<Ctrl+A>' if utils.is_mac else '<Meta+A>'),

        # Handling of Backtab
        ('', Qt.Key_Backtab, Qt.NoModifier, '', '<Backtab>'),
        ('', Qt.Key_Backtab, Qt.ShiftModifier, '', '<Shift+Tab>'),
        ('', Qt.Key_Backtab, Qt.AltModifier | Qt.ShiftModifier, '',
         '<Alt+Shift+Tab>'),

        # Stripping of Qt.GroupSwitchModifier
        ('', Qt.Key_A, Qt.GroupSwitchModifier, 'a', 'a'),
    ])
    def test_append_event(self, old, key, modifiers, text, expected):
        seq = keyutils.KeySequence.parse(old)
        event = QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)
        new = seq.append_event(event)
        assert new == keyutils.KeySequence.parse(expected)

    @pytest.mark.fake_os('mac')
    @pytest.mark.parametrize('modifiers, expected', [
        (Qt.ControlModifier,
         Qt.MetaModifier),
        (Qt.MetaModifier,
         Qt.ControlModifier),
        (Qt.ControlModifier | Qt.MetaModifier,
         Qt.ControlModifier | Qt.MetaModifier),
        (Qt.ControlModifier | Qt.ShiftModifier,
         Qt.MetaModifier | Qt.ShiftModifier),
        (Qt.MetaModifier | Qt.ShiftModifier,
         Qt.ControlModifier | Qt.ShiftModifier),
        (Qt.ShiftModifier, Qt.ShiftModifier),
    ])
    def test_fake_mac(self, fake_keyevent, modifiers, expected):
        """Make sure Control/Meta are swapped with a simulated Mac."""
        seq = keyutils.KeySequence()
        event = fake_keyevent(key=Qt.Key_A, modifiers=modifiers)
        new = seq.append_event(event)
        assert new[0] == keyutils.KeyInfo(Qt.Key_A, expected)

    @pytest.mark.parametrize('key', [Qt.Key_unknown, 0x0])
    def test_append_event_invalid(self, key):
        seq = keyutils.KeySequence()
        event = QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier, '')
        with pytest.raises(keyutils.KeyParseError):
            seq.append_event(event)

    def test_strip_modifiers(self):
        seq = keyutils.KeySequence(Qt.Key_0,
                                   Qt.Key_1 | Qt.KeypadModifier,
                                   Qt.Key_A | Qt.ControlModifier)
        expected = keyutils.KeySequence(Qt.Key_0,
                                        Qt.Key_1,
                                        Qt.Key_A | Qt.ControlModifier)
        assert seq.strip_modifiers() == expected

    def test_with_mappings(self):
        seq = keyutils.KeySequence.parse('foobar')
        mappings = {
            keyutils.KeySequence.parse('b'): keyutils.KeySequence.parse('t')
        }
        seq2 = seq.with_mappings(mappings)
        assert seq2 == keyutils.KeySequence.parse('footar')

    @pytest.mark.parametrize('keystr, expected', [
        ('<Ctrl-Alt-y>',
         keyutils.KeySequence(Qt.ControlModifier | Qt.AltModifier | Qt.Key_Y)),
        ('x', keyutils.KeySequence(Qt.Key_X)),
        ('X', keyutils.KeySequence(Qt.ShiftModifier | Qt.Key_X)),
        ('<Escape>', keyutils.KeySequence(Qt.Key_Escape)),
        ('xyz', keyutils.KeySequence(Qt.Key_X, Qt.Key_Y, Qt.Key_Z)),
        ('<Control-x><Meta-y>',
         keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X,
                              Qt.MetaModifier | Qt.Key_Y)),

        ('<Shift-x>', keyutils.KeySequence(Qt.ShiftModifier | Qt.Key_X)),
        ('<Alt-x>', keyutils.KeySequence(Qt.AltModifier | Qt.Key_X)),
        ('<Control-x>', keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X)),
        ('<Meta-x>', keyutils.KeySequence(Qt.MetaModifier | Qt.Key_X)),
        ('<Num-x>', keyutils.KeySequence(Qt.KeypadModifier | Qt.Key_X)),

        ('>', keyutils.KeySequence(Qt.Key_Greater)),
        ('<', keyutils.KeySequence(Qt.Key_Less)),
        ('a>', keyutils.KeySequence(Qt.Key_A, Qt.Key_Greater)),
        ('a<', keyutils.KeySequence(Qt.Key_A, Qt.Key_Less)),
        ('>a', keyutils.KeySequence(Qt.Key_Greater, Qt.Key_A)),
        ('<a', keyutils.KeySequence(Qt.Key_Less, Qt.Key_A)),
        ('<alt+greater>',
         keyutils.KeySequence(Qt.Key_Greater | Qt.AltModifier)),
        ('<alt+less>',
         keyutils.KeySequence(Qt.Key_Less | Qt.AltModifier)),

        ('<alt+<>', keyutils.KeyParseError),
        ('<alt+>>', keyutils.KeyParseError),
        ('<blub>', keyutils.KeyParseError),
        ('<>', keyutils.KeyParseError),
        ('\U00010000', keyutils.KeyParseError),
    ])
    def test_parse(self, keystr, expected):
        if expected is keyutils.KeyParseError:
            with pytest.raises(keyutils.KeyParseError):
                keyutils.KeySequence.parse(keystr)
        else:
            assert keyutils.KeySequence.parse(keystr) == expected

    @hypothesis.given(strategies.text())
    def test_parse_hypothesis(self, keystr):
        try:
            seq = keyutils.KeySequence.parse(keystr)
        except keyutils.KeyParseError:
            pass
        else:
            str(seq)


def test_key_info_from_event():
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.ShiftModifier, 'A')
    info = keyutils.KeyInfo.from_event(ev)
    assert info.key == Qt.Key_A
    assert info.modifiers == Qt.ShiftModifier


def test_key_info_to_event():
    info = keyutils.KeyInfo(Qt.Key_A, Qt.ShiftModifier)
    ev = info.to_event()
    assert ev.key() == Qt.Key_A
    assert ev.modifiers() == Qt.ShiftModifier
    assert ev.text() == 'A'


def test_key_info_to_int():
    info = keyutils.KeyInfo(Qt.Key_A, Qt.ShiftModifier)
    assert info.to_int() == Qt.Key_A | Qt.ShiftModifier


@pytest.mark.parametrize('key, printable', [
    (Qt.Key_Control, False),
    (Qt.Key_Escape, False),
    (Qt.Key_Tab, False),
    (Qt.Key_Backtab, False),
    (Qt.Key_Backspace, False),
    (Qt.Key_Return, False),
    (Qt.Key_Enter, False),
    (Qt.Key_Space, False),
    (0x0, False),  # Used by Qt for unknown keys

    (Qt.Key_ydiaeresis, True),
    (Qt.Key_X, True),
])
def test_is_printable(key, printable):
    assert keyutils._is_printable(key) == printable
    assert keyutils.is_special(key, Qt.NoModifier) != printable


@pytest.mark.parametrize('key, modifiers, special', [
    (Qt.Key_Escape, Qt.NoModifier, True),
    (Qt.Key_Escape, Qt.ShiftModifier, True),
    (Qt.Key_Escape, Qt.ControlModifier, True),
    (Qt.Key_X, Qt.ControlModifier, True),
    (Qt.Key_X, Qt.NoModifier, False),
    (Qt.Key_2, Qt.NoModifier, False),

    # Keypad should not reset hint keychain - see #3735
    (Qt.Key_2, Qt.KeypadModifier, False),

    # Modifiers should not reset hint keychain - see #4264
    (Qt.Key_Shift, Qt.ShiftModifier, False),
    (Qt.Key_Control, Qt.ControlModifier, False),
    (Qt.Key_Alt, Qt.AltModifier, False),
    (Qt.Key_Meta, Qt.MetaModifier, False),
    (Qt.Key_Mode_switch, Qt.GroupSwitchModifier, False),
])
def test_is_special_hint_mode(key, modifiers, special):
    assert keyutils.is_special_hint_mode(key, modifiers) == special


@pytest.mark.parametrize('key, modifiers, special', [
    (Qt.Key_Escape, Qt.NoModifier, True),
    (Qt.Key_Escape, Qt.ShiftModifier, True),
    (Qt.Key_Escape, Qt.ControlModifier, True),
    (Qt.Key_X, Qt.ControlModifier, True),
    (Qt.Key_X, Qt.NoModifier, False),
    (Qt.Key_2, Qt.KeypadModifier, True),
    (Qt.Key_2, Qt.NoModifier, False),
    (Qt.Key_Shift, Qt.ShiftModifier, True),
    (Qt.Key_Control, Qt.ControlModifier, True),
    (Qt.Key_Alt, Qt.AltModifier, True),
    (Qt.Key_Meta, Qt.MetaModifier, True),
    (Qt.Key_Mode_switch, Qt.GroupSwitchModifier, True),
])
def test_is_special(key, modifiers, special):
    assert keyutils.is_special(key, modifiers) == special


@pytest.mark.parametrize('key, ismodifier', [
    (Qt.Key_Control, True),
    (Qt.Key_X, False),
    (Qt.Key_Super_L, False),  # Modifier but not in _MODIFIER_MAP
])
def test_is_modifier_key(key, ismodifier):
    assert keyutils.is_modifier_key(key) == ismodifier


@pytest.mark.parametrize('func', [
    keyutils._assert_plain_key,
    keyutils._assert_plain_modifier,
    keyutils._is_printable,
    keyutils.is_modifier_key,
    keyutils._key_to_string,
    keyutils._modifiers_to_string,
])
def test_non_plain(func):
    with pytest.raises(AssertionError):
        func(Qt.Key_X | Qt.ControlModifier)
