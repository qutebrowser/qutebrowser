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

import operator

import pytest
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QKeySequence
from PyQt5.QtWidgets import QWidget

from tests.unit.keyinput import key_data
from qutebrowser.keyinput import keyutils


@pytest.fixture(params=key_data.KEYS, ids=lambda k: k.attribute)
def qt_key(request):
    """Get all existing keys from key_data.py.

    Keys which don't exist with this Qt version result in skipped tests.
    """
    key = request.param
    if key.member is None:
        pytest.skip("Did not find key {}".format(key.attribute))
    return key


@pytest.fixture(params=[key for key in key_data.KEYS if key.qtest],
                ids=lambda k: k.attribute)
def qtest_key(request):
    """Get keys from key_data.py which can be used with QTest."""
    return request.param


def test_key_data():
    """Make sure all possible keys are in key_data.KEYS."""
    key_names = {name[len("Key_"):]
                 for name, value in sorted(vars(Qt).items())
                 if isinstance(value, Qt.Key)}
    key_data_names = {key.attribute for key in sorted(key_data.KEYS)}
    diff = key_names - key_data_names
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

    (Qt.Key_Shift, Qt.ShiftModifier, '<Shift>'),
    (Qt.Key_Shift, Qt.ShiftModifier | Qt.ControlModifier, '<Ctrl+Shift>'),
])
def test_key_info_str(key, modifiers, expected):
    assert str(keyutils.KeyInfo(key, modifiers)) == expected


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

    def test_init_unknown(self):
        with pytest.raises(keyutils.KeyParseError):
            keyutils.KeySequence(Qt.Key_unknown)

    def test_init_invalid(self):
        with pytest.raises(AssertionError):
            keyutils.KeySequence(-1)

    @pytest.mark.parametrize('orig, normalized', [
        ('<Control+x>', '<Ctrl+x>'),
        ('<Windows+x>', '<Meta+x>'),
        ('<Mod1+x>', '<Alt+x>'),
        ('<Mod4+x>', '<Meta+x>'),
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

    @pytest.mark.parametrize('entered, configured, expected', [
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
        ('a', '', QKeySequence.NoMatch),
    ])
    def test_matches(self, entered, configured, expected):
        entered = keyutils.KeySequence.parse(entered)
        configured = keyutils.KeySequence.parse(configured)
        assert entered.matches(configured) == expected

    @pytest.mark.parametrize('old, key, modifiers, text, expected', [
        ('a', Qt.Key_B, Qt.NoModifier, 'b', 'ab'),
        ('a', Qt.Key_B, Qt.ShiftModifier, 'B', 'aB'),
        ('a', Qt.Key_B, Qt.ControlModifier | Qt.ShiftModifier, 'B',
         'a<Ctrl+Shift+b>'),

        # Modifier stripping with symbols
        ('', Qt.Key_Colon, Qt.NoModifier, ':', ':'),
        ('', Qt.Key_Colon, Qt.ShiftModifier, ':', ':'),
        ('', Qt.Key_Colon, Qt.ControlModifier | Qt.ShiftModifier, ':',
         '<Ctrl+Shift+:>'),

        # Handling of Backtab
        ('', Qt.Key_Backtab, Qt.NoModifier, '', '<Backtab>'),
        ('', Qt.Key_Backtab, Qt.ShiftModifier, '', '<Shift+Tab>'),
        ('', Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier, '',
         '<Control+Shift+Tab>'),
    ])
    def test_append_event(self, old, key, modifiers, text, expected):
        seq = keyutils.KeySequence.parse(old)
        event = QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)
        new = seq.append_event(event)
        assert new == keyutils.KeySequence.parse(expected)

    @pytest.mark.parametrize('keystr, expected', [
        ('<Control-x>', keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X)),
        ('<Meta-x>', keyutils.KeySequence(Qt.MetaModifier | Qt.Key_X)),
        ('<Ctrl-Alt-y>',
         keyutils.KeySequence(Qt.ControlModifier | Qt.AltModifier | Qt.Key_Y)),
        ('x', keyutils.KeySequence(Qt.Key_X)),
        ('X', keyutils.KeySequence(Qt.ShiftModifier | Qt.Key_X)),
        ('<Escape>', keyutils.KeySequence(Qt.Key_Escape)),
        ('xyz', keyutils.KeySequence(Qt.Key_X, Qt.Key_Y, Qt.Key_Z)),
        ('<Control-x><Meta-y>',
         keyutils.KeySequence(Qt.ControlModifier | Qt.Key_X,
                              Qt.MetaModifier | Qt.Key_Y)),
        ('<blub>', keyutils.KeyParseError),
        ('\U00010000', keyutils.KeyParseError),
    ])
    def test_parse(self, keystr, expected):
        if expected is keyutils.KeyParseError:
            with pytest.raises(keyutils.KeyParseError):
                keyutils.KeySequence.parse(keystr)
        else:
            assert keyutils.KeySequence.parse(keystr) == expected


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


@pytest.mark.parametrize('key, printable', [
    (Qt.Key_Control, False),
    (Qt.Key_Escape, False),
    (Qt.Key_Tab, False),
    (Qt.Key_Backtab, False),
    (Qt.Key_Backspace, False),
    (Qt.Key_Return, False),
    (Qt.Key_Enter, False),
    (Qt.Key_Space, False),
    (Qt.Key_X | Qt.ControlModifier, False),  # Wrong usage

    (Qt.Key_ydiaeresis, True),
    (Qt.Key_X, True),
])
def test_is_printable(key, printable):
    assert keyutils.is_printable(key) == printable


@pytest.mark.parametrize('key, ismodifier', [
    (Qt.Key_Control, True),
    (Qt.Key_X, False),
    (Qt.Key_Super_L, False),  # Modifier but not in _MODIFIER_MAP
])
def test_is_modifier_key(key, ismodifier):
    assert keyutils.is_modifier_key(key) == ismodifier
