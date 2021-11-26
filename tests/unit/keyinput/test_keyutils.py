# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import operator

import hypothesis
from hypothesis import strategies
import pytest
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QWidget

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
                 value not in [Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeyboardModifierMask]}
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
        modifiers = Qt.KeyboardModifier.ShiftModifier if upper else Qt.KeyboardModifiers()
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
        assert keyutils._key_to_string(Qt.Key.Key_A) == 'A'


@pytest.mark.parametrize('key, modifiers, expected', [
    (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, 'a'),
    (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, 'A'),

    (Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, '<Space>'),
    (Qt.Key.Key_Space, Qt.KeyboardModifier.ShiftModifier, '<Shift+Space>'),
    (Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier, '<Shift+Tab>'),
    (Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier, '<Ctrl+a>'),
    (Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, '<Ctrl+Shift+a>'),
    (Qt.Key.Key_A,
     Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier,
     '<Meta+Ctrl+Alt+Shift+a>'),
    (ord('Œ'), Qt.KeyboardModifier.NoModifier, '<Œ>'),
    (ord('Œ'), Qt.KeyboardModifier.ShiftModifier, '<Shift+Œ>'),
    (ord('Œ'), Qt.KeyboardModifier.GroupSwitchModifier, '<AltGr+Œ>'),
    (ord('Œ'), Qt.KeyboardModifier.GroupSwitchModifier | Qt.KeyboardModifier.ShiftModifier, '<AltGr+Shift+Œ>'),

    (Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier, '<Shift>'),
    (Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier, '<Ctrl+Shift>'),
    (Qt.Key.Key_Alt, Qt.KeyboardModifier.AltModifier, '<Alt>'),
    (Qt.Key.Key_Shift, Qt.KeyboardModifier.GroupSwitchModifier | Qt.KeyboardModifier.ShiftModifier, '<AltGr+Shift>'),
    (Qt.Key.Key_AltGr, Qt.KeyboardModifier.GroupSwitchModifier, '<AltGr>'),
])
def test_key_info_str(key, modifiers, expected):
    assert str(keyutils.KeyInfo(key, modifiers)) == expected


@pytest.mark.parametrize('info1, info2, equal', [
    (keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
     keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
     True),
    (keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
     keyutils.KeyInfo(Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier),
     False),
    (keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
     keyutils.KeyInfo(Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier),
     False),
])
def test_hash(info1, info2, equal):
    assert (hash(info1) == hash(info2)) == equal


@pytest.mark.parametrize('key, modifiers, text, expected', [
    (0xd83c, Qt.KeyboardModifier.NoModifier, '🏻', '<🏻>'),
    (0xd867, Qt.KeyboardModifier.NoModifier, '𩷶', '<𩷶>'),
    (0xd867, Qt.KeyboardModifier.ShiftModifier, '𩷶', '<Shift+𩷶>'),
])
def test_surrogates(key, modifiers, text, expected):
    evt = QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)
    assert str(keyutils.KeyInfo.from_event(evt)) == expected


@pytest.mark.parametrize('keys, expected', [
    ([0x1f3fb], '<🏻>'),
    ([0x29df6], '<𩷶>'),
    ([Qt.Key.Key_Shift, 0x29df6], '<Shift><𩷶>'),
    ([0x1f468, 0x200d, 0x1f468, 0x200d, 0x1f466], '<👨><‍><👨><‍><👦>'),
])
def test_surrogate_sequences(keys, expected):
    seq = keyutils.KeySequence(*keys)
    assert str(seq) == expected


# This shouldn't happen, but if it does we should handle it well
def test_surrogate_error():
    evt = QKeyEvent(QKeyEvent.KeyPress, 0xd83e, Qt.KeyboardModifier.NoModifier, '🤞🏻')
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
        seq = keyutils.KeySequence(Qt.Key.Key_A, Qt.Key.Key_B, Qt.Key.Key_C, Qt.Key.Key_D,
                                   Qt.Key.Key_E)
        assert len(seq._sequences) == 2
        assert len(seq._sequences[0]) == 4
        assert len(seq._sequences[1]) == 1

    def test_init_empty(self):
        seq = keyutils.KeySequence()
        assert not seq

    @pytest.mark.parametrize('key', [Qt.Key.Key_unknown, -1, 0])
    def test_init_unknown(self, key):
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence(key)

    def test_parse_unknown(self):
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence.parse('\x1f')

    @pytest.mark.parametrize('orig, normalized', [
        ('<Control+x>', '<Ctrl+x>'),
        ('<Windows+x>', '<Meta+x>'),
        ('<Super+x>', '<Meta+x>'),
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
        seq = keyutils.KeySequence(Qt.Key.Key_A | Qt.KeyboardModifier.ControlModifier,
                                   Qt.Key.Key_B | Qt.KeyboardModifier.ShiftModifier,
                                   Qt.Key.Key_C,
                                   Qt.Key.Key_D,
                                   Qt.Key.Key_E)
        expected = [keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier),
                    keyutils.KeyInfo(Qt.Key.Key_B, Qt.KeyboardModifier.ShiftModifier),
                    keyutils.KeyInfo(Qt.Key.Key_C, Qt.KeyboardModifier.NoModifier),
                    keyutils.KeyInfo(Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier),
                    keyutils.KeyInfo(Qt.Key.Key_E, Qt.KeyboardModifier.NoModifier)]
        assert list(seq) == expected

    def test_repr(self):
        seq = keyutils.KeySequence(Qt.Key.Key_A | Qt.KeyboardModifier.ControlModifier,
                                   Qt.Key.Key_B | Qt.KeyboardModifier.ShiftModifier)
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
        expected = keyutils.KeyInfo(Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier)
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
        ('abc', 'abcd', QKeySequence.SequenceMatch.PartialMatch),
        ('abcd', 'abcd', QKeySequence.SequenceMatch.ExactMatch),
        ('ax', 'abcd', QKeySequence.SequenceMatch.NoMatch),
        ('abcdef', 'abcd', QKeySequence.SequenceMatch.NoMatch),

        # config: abcd ef
        ('abc', 'abcdef', QKeySequence.SequenceMatch.PartialMatch),
        ('abcde', 'abcdef', QKeySequence.SequenceMatch.PartialMatch),
        ('abcd', 'abcdef', QKeySequence.SequenceMatch.PartialMatch),
        ('abcdx', 'abcdef', QKeySequence.SequenceMatch.NoMatch),
        ('ax', 'abcdef', QKeySequence.SequenceMatch.NoMatch),
        ('abcdefg', 'abcdef', QKeySequence.SequenceMatch.NoMatch),
        ('abcdef', 'abcdef', QKeySequence.SequenceMatch.ExactMatch),

        # other examples
        ('ab', 'a', QKeySequence.SequenceMatch.NoMatch),

        # empty strings
        ('', '', QKeySequence.SequenceMatch.ExactMatch),
        ('', 'a', QKeySequence.SequenceMatch.PartialMatch),
        ('a', '', QKeySequence.SequenceMatch.NoMatch)]

    @pytest.mark.parametrize('entered, configured, match_type', MATCH_TESTS)
    def test_matches(self, entered, configured, match_type):
        entered = keyutils.KeySequence.parse(entered)
        configured = keyutils.KeySequence.parse(configured)
        assert entered.matches(configured) == match_type

    @pytest.mark.parametrize('old, key, modifiers, text, expected', [
        ('a', Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier, 'b', 'ab'),
        ('a', Qt.Key.Key_B, Qt.KeyboardModifier.ShiftModifier, 'B', 'aB'),
        ('a', Qt.Key.Key_B, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier, 'B',
         'a<Alt+Shift+b>'),

        # Modifier stripping with symbols
        ('', Qt.Key.Key_Colon, Qt.KeyboardModifier.NoModifier, ':', ':'),
        ('', Qt.Key.Key_Colon, Qt.KeyboardModifier.ShiftModifier, ':', ':'),
        ('', Qt.Key.Key_Colon, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier, ':',
         '<Alt+Shift+:>'),

        # Swapping Control/Meta on macOS
        ('', Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier, '',
         '<Meta+A>' if utils.is_mac else '<Ctrl+A>'),
        ('', Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, '',
         '<Meta+Shift+A>' if utils.is_mac else '<Ctrl+Shift+A>'),
        ('', Qt.Key.Key_A, Qt.KeyboardModifier.MetaModifier, '',
         '<Ctrl+A>' if utils.is_mac else '<Meta+A>'),

        # Handling of Backtab
        ('', Qt.Key.Key_Backtab, Qt.KeyboardModifier.NoModifier, '', '<Backtab>'),
        ('', Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier, '', '<Shift+Tab>'),
        ('', Qt.Key.Key_Backtab, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier, '',
         '<Alt+Shift+Tab>'),

        # Stripping of Qt.KeyboardModifier.GroupSwitchModifier
        ('', Qt.Key.Key_A, Qt.KeyboardModifier.GroupSwitchModifier, 'a', 'a'),
    ])
    def test_append_event(self, old, key, modifiers, text, expected):
        seq = keyutils.KeySequence.parse(old)
        event = QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)
        new = seq.append_event(event)
        assert new == keyutils.KeySequence.parse(expected)

    @pytest.mark.fake_os('mac')
    @pytest.mark.parametrize('modifiers, expected', [
        (Qt.KeyboardModifier.ControlModifier,
         Qt.KeyboardModifier.MetaModifier),
        (Qt.KeyboardModifier.MetaModifier,
         Qt.KeyboardModifier.ControlModifier),
        (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier,
         Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier),
        (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
         Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier),
        (Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier,
         Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier),
        (Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.ShiftModifier),
    ])
    def test_fake_mac(self, modifiers, expected):
        """Make sure Control/Meta are swapped with a simulated Mac."""
        seq = keyutils.KeySequence()
        info = keyutils.KeyInfo(key=Qt.Key.Key_A, modifiers=modifiers)
        new = seq.append_event(info.to_event())
        assert new[0] == keyutils.KeyInfo(Qt.Key.Key_A, expected)

    @pytest.mark.parametrize('key', [Qt.Key.Key_unknown, 0x0])
    def test_append_event_invalid(self, key):
        seq = keyutils.KeySequence()
        event = QKeyEvent(QKeyEvent.KeyPress, key, Qt.KeyboardModifier.NoModifier, '')
        with pytest.raises(keyutils.KeyParseError):
            seq.append_event(event)

    def test_strip_modifiers(self):
        seq = keyutils.KeySequence(Qt.Key.Key_0,
                                   Qt.Key.Key_1 | Qt.KeyboardModifier.KeypadModifier,
                                   Qt.Key.Key_A | Qt.KeyboardModifier.ControlModifier)
        expected = keyutils.KeySequence(Qt.Key.Key_0,
                                        Qt.Key.Key_1,
                                        Qt.Key.Key_A | Qt.KeyboardModifier.ControlModifier)
        assert seq.strip_modifiers() == expected

    @pytest.mark.parametrize('inp, mappings, expected', [
        ('foobar', {'b': 't'}, 'footar'),
        ('foo<Ctrl+x>bar', {'<Ctrl+x>': '<Ctrl+y>'}, 'foo<Ctrl+y>bar'),
        ('foobar', {'b': 'sa'}, 'foosaar'),
    ])
    def test_with_mappings(self, inp, mappings, expected):
        seq = keyutils.KeySequence.parse(inp)
        seq2 = seq.with_mappings({
            keyutils.KeySequence.parse(k): keyutils.KeySequence.parse(v)
            for k, v in mappings.items()
        })
        assert seq2 == keyutils.KeySequence.parse(expected)

    @pytest.mark.parametrize('keystr, expected', [
        # FIXME figure out why keys without modifier trigger an assertion
        ('<Ctrl-Alt-y>',
         keyutils.KeySequence(Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Y)),
        #('x', keyutils.KeySequence(Qt.Key.Key_X)),
        ('X', keyutils.KeySequence(Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_X)),
        #('<Escape>', keyutils.KeySequence(Qt.Key.Key_Escape)),
        #('xyz', keyutils.KeySequence(Qt.Key.Key_X, Qt.Key.Key_Y, Qt.Key.Key_Z)),
        ('<Control-x><Meta-y>',
         keyutils.KeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_X,
                              Qt.KeyboardModifier.MetaModifier | Qt.Key.Key_Y)),

        ('<Shift-x>', keyutils.KeySequence(Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_X)),
        ('<Alt-x>', keyutils.KeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_X)),
        ('<Control-x>', keyutils.KeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_X)),
        ('<Meta-x>', keyutils.KeySequence(Qt.KeyboardModifier.MetaModifier | Qt.Key.Key_X)),
        ('<Num-x>', keyutils.KeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_X)),

        #('>', keyutils.KeySequence(Qt.Key.Key_Greater)),
        #('<', keyutils.KeySequence(Qt.Key.Key_Less)),
        #('a>', keyutils.KeySequence(Qt.Key.Key_A, Qt.Key.Key_Greater)),
        #('a<', keyutils.KeySequence(Qt.Key.Key_A, Qt.Key.Key_Less)),
        #('>a', keyutils.KeySequence(Qt.Key.Key_Greater, Qt.Key.Key_A)),
        #('<a', keyutils.KeySequence(Qt.Key.Key_Less, Qt.Key.Key_A)),
        ('<alt+greater>',
         keyutils.KeySequence(Qt.Key.Key_Greater | Qt.KeyboardModifier.AltModifier)),
        ('<alt+less>',
         keyutils.KeySequence(Qt.Key.Key_Less | Qt.KeyboardModifier.AltModifier)),

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
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, 'A')
    info = keyutils.KeyInfo.from_event(ev)
    assert info.key == Qt.Key.Key_A
    assert info.modifiers == Qt.KeyboardModifier.ShiftModifier


def test_key_info_to_event():
    info = keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
    ev = info.to_event()
    assert ev.key() == Qt.Key.Key_A
    assert ev.modifiers() == Qt.KeyboardModifier.ShiftModifier
    assert ev.text() == 'A'


def test_key_info_to_int():
    info = keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
    assert info.to_int() == Qt.Key.Key_A | Qt.KeyboardModifier.ShiftModifier


@pytest.mark.parametrize('key, printable', [
    (Qt.Key.Key_Control, False),
    (Qt.Key.Key_Escape, False),
    (Qt.Key.Key_Tab, False),
    (Qt.Key.Key_Backtab, False),
    (Qt.Key.Key_Backspace, False),
    (Qt.Key.Key_Return, False),
    (Qt.Key.Key_Enter, False),
    (Qt.Key.Key_Space, False),
    (0x0, False),  # Used by Qt for unknown keys

    (Qt.Key.Key_ydiaeresis, True),
    (Qt.Key.Key_X, True),
])
def test_is_printable(key, printable):
    assert keyutils._is_printable(key) == printable
    assert keyutils.is_special(key, Qt.KeyboardModifier.NoModifier) != printable


@pytest.mark.parametrize('key, modifiers, special', [
    (Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier, True),
    (Qt.Key.Key_Escape, Qt.KeyboardModifier.ShiftModifier, True),
    (Qt.Key.Key_Escape, Qt.KeyboardModifier.ControlModifier, True),
    (Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier, True),
    (Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier, False),
    (Qt.Key.Key_2, Qt.KeyboardModifier.KeypadModifier, True),
    (Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, False),
    (Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier, True),
    (Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier, True),
    (Qt.Key.Key_Alt, Qt.KeyboardModifier.AltModifier, True),
    (Qt.Key.Key_Meta, Qt.KeyboardModifier.MetaModifier, True),
    (Qt.Key.Key_Mode_switch, Qt.KeyboardModifier.GroupSwitchModifier, True),
])
def test_is_special(key, modifiers, special):
    assert keyutils.is_special(key, modifiers) == special


@pytest.mark.parametrize('key, ismodifier', [
    (Qt.Key.Key_Control, True),
    (Qt.Key.Key_X, False),
    (Qt.Key.Key_Super_L, False),  # Modifier but not in _MODIFIER_MAP
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
        func(Qt.Key.Key_X | Qt.KeyboardModifier.ControlModifier)
