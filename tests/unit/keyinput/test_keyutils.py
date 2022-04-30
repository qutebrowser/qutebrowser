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
from qutebrowser.qt import QtWidgets

from unit.keyinput import key_data
from qutebrowser.keyinput import keyutils
from qutebrowser.utils import utils
from qutebrowser.qt import QtGui, QtCore


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
    key_names = {
        name[len("Key_") :]
        for name, value in sorted(vars(QtCore.Qt).items())
        if isinstance(value, QtCore.Qt.Key)
    }
    key_data_names = {key.attribute for key in sorted(key_data.KEYS)}
    diff = key_names - key_data_names
    assert not diff


def test_key_data_modifiers():
    """Make sure all possible modifiers are in key_data.MODIFIERS."""
    mod_names = {
        name[: -len("Modifier")]
        for name, value in sorted(vars(QtCore.Qt).items())
        if isinstance(value, QtCore.Qt.KeyboardModifier)
        and value not in [QtCore.Qt.NoModifier, QtCore.Qt.KeyboardModifierMask]
    }
    mod_data_names = {mod.attribute for mod in sorted(key_data.MODIFIERS)}
    diff = mod_names - mod_data_names
    assert not diff


class KeyTesterWidget(QtWidgets.QWidget):

    """Widget to get the text of QKeyPressEvents.

    This is done so we can check QTest::keyToAscii (qasciikey.cpp) as we can't
    call that directly, only via QTest::keyPress.
    """

    got_text = QtCore.pyqtSignal()

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
        modifiers = QtCore.Qt.ShiftModifier if upper else QtCore.Qt.KeyboardModifiers()
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

        info = keyutils.KeyInfo(
            qtest_key.member, modifiers=QtCore.Qt.KeyboardModifiers()
        )
        assert info.text() == key_tester.text.lower()


class TestKeyToString:

    def test_to_string(self, qt_key):
        assert keyutils._key_to_string(qt_key.member) == qt_key.name

    def test_modifiers_to_string(self, qt_mod):
        expected = qt_mod.name + '+'
        assert keyutils._modifiers_to_string(qt_mod.member) == expected

    def test_missing(self, monkeypatch):
        monkeypatch.delattr(keyutils.QtCore.Qt, 'Key_AltGr')
        # We don't want to test the key which is actually missing - we only
        # want to know if the mapping still behaves properly.
        assert keyutils._key_to_string(QtCore.Qt.Key_A) == 'A'


@pytest.mark.parametrize(
    'key, modifiers, expected',
    [
        (QtCore.Qt.Key_A, QtCore.Qt.NoModifier, 'a'),
        (QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier, 'A'),
        (QtCore.Qt.Key_Space, QtCore.Qt.NoModifier, '<Space>'),
        (QtCore.Qt.Key_Space, QtCore.Qt.ShiftModifier, '<Shift+Space>'),
        (QtCore.Qt.Key_Tab, QtCore.Qt.ShiftModifier, '<Shift+Tab>'),
        (QtCore.Qt.Key_A, QtCore.Qt.ControlModifier, '<Ctrl+a>'),
        (
            QtCore.Qt.Key_A,
            QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier,
            '<Ctrl+Shift+a>',
        ),
        (
            QtCore.Qt.Key_A,
            QtCore.Qt.ControlModifier
            | QtCore.Qt.AltModifier
            | QtCore.Qt.MetaModifier
            | QtCore.Qt.ShiftModifier,
            '<Meta+Ctrl+Alt+Shift+a>',
        ),
        (ord('Œ'), QtCore.Qt.NoModifier, '<Œ>'),
        (ord('Œ'), QtCore.Qt.ShiftModifier, '<Shift+Œ>'),
        (ord('Œ'), QtCore.Qt.GroupSwitchModifier, '<AltGr+Œ>'),
        (
            ord('Œ'),
            QtCore.Qt.GroupSwitchModifier | QtCore.Qt.ShiftModifier,
            '<AltGr+Shift+Œ>',
        ),
        (QtCore.Qt.Key_Shift, QtCore.Qt.ShiftModifier, '<Shift>'),
        (
            QtCore.Qt.Key_Shift,
            QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier,
            '<Ctrl+Shift>',
        ),
        (QtCore.Qt.Key_Alt, QtCore.Qt.AltModifier, '<Alt>'),
        (
            QtCore.Qt.Key_Shift,
            QtCore.Qt.GroupSwitchModifier | QtCore.Qt.ShiftModifier,
            '<AltGr+Shift>',
        ),
        (QtCore.Qt.Key_AltGr, QtCore.Qt.GroupSwitchModifier, '<AltGr>'),
    ],
)
def test_key_info_str(key, modifiers, expected):
    assert str(keyutils.KeyInfo(key, modifiers)) == expected


@pytest.mark.parametrize(
    'info1, info2, equal',
    [
        (
            keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.NoModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.NoModifier),
            True,
        ),
        (
            keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.NoModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_B, QtCore.Qt.NoModifier),
            False,
        ),
        (
            keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.NoModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_B, QtCore.Qt.ControlModifier),
            False,
        ),
    ],
)
def test_hash(info1, info2, equal):
    assert (hash(info1) == hash(info2)) == equal


@pytest.mark.parametrize(
    'key, modifiers, text, expected',
    [
        (0xD83C, QtCore.Qt.NoModifier, '🏻', '<🏻>'),
        (0xD867, QtCore.Qt.NoModifier, '𩷶', '<𩷶>'),
        (0xD867, QtCore.Qt.ShiftModifier, '𩷶', '<Shift+𩷶>'),
    ],
)
def test_surrogates(key, modifiers, text, expected):
    evt = QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, modifiers, text)
    assert str(keyutils.KeyInfo.from_event(evt)) == expected


@pytest.mark.parametrize(
    'keys, expected',
    [
        ([0x1F3FB], '<🏻>'),
        ([0x29DF6], '<𩷶>'),
        ([QtCore.Qt.Key_Shift, 0x29DF6], '<Shift><𩷶>'),
        ([0x1F468, 0x200D, 0x1F468, 0x200D, 0x1F466], '<👨><‍><👨><‍><👦>'),
    ],
)
def test_surrogate_sequences(keys, expected):
    seq = keyutils.KeySequence(*keys)
    assert str(seq) == expected


# This shouldn't happen, but if it does we should handle it well
def test_surrogate_error():
    evt = QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, 0xD83E, QtCore.Qt.NoModifier, '🤞🏻')
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
        seq = keyutils.KeySequence(
            QtCore.Qt.Key_A,
            QtCore.Qt.Key_B,
            QtCore.Qt.Key_C,
            QtCore.Qt.Key_D,
            QtCore.Qt.Key_E,
        )
        assert len(seq._sequences) == 2
        assert len(seq._sequences[0]) == 4
        assert len(seq._sequences[1]) == 1

    def test_init_empty(self):
        seq = keyutils.KeySequence()
        assert not seq

    @pytest.mark.parametrize('key', [QtCore.Qt.Key_unknown, -1, 0])
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
        seq = keyutils.KeySequence(
            QtCore.Qt.Key_A | QtCore.Qt.ControlModifier,
            QtCore.Qt.Key_B | QtCore.Qt.ShiftModifier,
            QtCore.Qt.Key_C,
            QtCore.Qt.Key_D,
            QtCore.Qt.Key_E,
        )
        expected = [
            keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.ControlModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_B, QtCore.Qt.ShiftModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_C, QtCore.Qt.NoModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_D, QtCore.Qt.NoModifier),
            keyutils.KeyInfo(QtCore.Qt.Key_E, QtCore.Qt.NoModifier),
        ]
        assert list(seq) == expected

    def test_repr(self):
        seq = keyutils.KeySequence(
            QtCore.Qt.Key_A | QtCore.Qt.ControlModifier,
            QtCore.Qt.Key_B | QtCore.Qt.ShiftModifier,
        )
        assert repr(seq) == (
            "<qutebrowser.keyinput.keyutils.KeySequence " "keys='<Ctrl+a>B'>"
        )

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
        expected = keyutils.KeyInfo(QtCore.Qt.Key_B, QtCore.Qt.NoModifier)
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
        ('abc', 'abcd', QtGui.QKeySequence.PartialMatch),
        ('abcd', 'abcd', QtGui.QKeySequence.ExactMatch),
        ('ax', 'abcd', QtGui.QKeySequence.NoMatch),
        ('abcdef', 'abcd', QtGui.QKeySequence.NoMatch),

        # config: abcd ef
        ('abc', 'abcdef', QtGui.QKeySequence.PartialMatch),
        ('abcde', 'abcdef', QtGui.QKeySequence.PartialMatch),
        ('abcd', 'abcdef', QtGui.QKeySequence.PartialMatch),
        ('abcdx', 'abcdef', QtGui.QKeySequence.NoMatch),
        ('ax', 'abcdef', QtGui.QKeySequence.NoMatch),
        ('abcdefg', 'abcdef', QtGui.QKeySequence.NoMatch),
        ('abcdef', 'abcdef', QtGui.QKeySequence.ExactMatch),

        # other examples
        ('ab', 'a', QtGui.QKeySequence.NoMatch),

        # empty strings
        ('', '', QtGui.QKeySequence.ExactMatch),
        ('', 'a', QtGui.QKeySequence.PartialMatch),
        ('a', '', QtGui.QKeySequence.NoMatch),
    ]

    @pytest.mark.parametrize('entered, configured, match_type', MATCH_TESTS)
    def test_matches(self, entered, configured, match_type):
        entered = keyutils.KeySequence.parse(entered)
        configured = keyutils.KeySequence.parse(configured)
        assert entered.matches(configured) == match_type

    @pytest.mark.parametrize(
        'old, key, modifiers, text, expected',
        [
            ('a', QtCore.Qt.Key_B, QtCore.Qt.NoModifier, 'b', 'ab'),
            ('a', QtCore.Qt.Key_B, QtCore.Qt.ShiftModifier, 'B', 'aB'),
            (
                'a',
                QtCore.Qt.Key_B,
                QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier,
                'B',
                'a<Alt+Shift+b>',
            ),
            # Modifier stripping with symbols
            ('', QtCore.Qt.Key_Colon, QtCore.Qt.NoModifier, ':', ':'),
            ('', QtCore.Qt.Key_Colon, QtCore.Qt.ShiftModifier, ':', ':'),
            (
                '',
                QtCore.Qt.Key_Colon,
                QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier,
                ':',
                '<Alt+Shift+:>',
            ),
            # Swapping Control/Meta on macOS
            (
                '',
                QtCore.Qt.Key_A,
                QtCore.Qt.ControlModifier,
                '',
                '<Meta+A>' if utils.is_mac else '<Ctrl+A>',
            ),
            (
                '',
                QtCore.Qt.Key_A,
                QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier,
                '',
                '<Meta+Shift+A>' if utils.is_mac else '<Ctrl+Shift+A>',
            ),
            (
                '',
                QtCore.Qt.Key_A,
                QtCore.Qt.MetaModifier,
                '',
                '<Ctrl+A>' if utils.is_mac else '<Meta+A>',
            ),
            # Handling of Backtab
            ('', QtCore.Qt.Key_Backtab, QtCore.Qt.NoModifier, '', '<Backtab>'),
            ('', QtCore.Qt.Key_Backtab, QtCore.Qt.ShiftModifier, '', '<Shift+Tab>'),
            (
                '',
                QtCore.Qt.Key_Backtab,
                QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier,
                '',
                '<Alt+Shift+Tab>',
            ),
            # Stripping of Qt.GroupSwitchModifier
            ('', QtCore.Qt.Key_A, QtCore.Qt.GroupSwitchModifier, 'a', 'a'),
        ],
    )
    def test_append_event(self, old, key, modifiers, text, expected):
        seq = keyutils.KeySequence.parse(old)
        event = QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, modifiers, text)
        new = seq.append_event(event)
        assert new == keyutils.KeySequence.parse(expected)

    @pytest.mark.fake_os('mac')
    @pytest.mark.parametrize(
        'modifiers, expected',
        [
            (QtCore.Qt.ControlModifier, QtCore.Qt.MetaModifier),
            (QtCore.Qt.MetaModifier, QtCore.Qt.ControlModifier),
            (
                QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier,
                QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier,
            ),
            (
                QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier,
                QtCore.Qt.MetaModifier | QtCore.Qt.ShiftModifier,
            ),
            (
                QtCore.Qt.MetaModifier | QtCore.Qt.ShiftModifier,
                QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier,
            ),
            (QtCore.Qt.ShiftModifier, QtCore.Qt.ShiftModifier),
        ],
    )
    def test_fake_mac(self, modifiers, expected):
        """Make sure Control/Meta are swapped with a simulated Mac."""
        seq = keyutils.KeySequence()
        info = keyutils.KeyInfo(key=QtCore.Qt.Key_A, modifiers=modifiers)
        new = seq.append_event(info.to_event())
        assert new[0] == keyutils.KeyInfo(QtCore.Qt.Key_A, expected)

    @pytest.mark.parametrize('key', [QtCore.Qt.Key_unknown, 0x0])
    def test_append_event_invalid(self, key):
        seq = keyutils.KeySequence()
        event = QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, QtCore.Qt.NoModifier, '')
        with pytest.raises(keyutils.KeyParseError):
            seq.append_event(event)

    def test_strip_modifiers(self):
        seq = keyutils.KeySequence(
            QtCore.Qt.Key_0,
            QtCore.Qt.Key_1 | QtCore.Qt.KeypadModifier,
            QtCore.Qt.Key_A | QtCore.Qt.ControlModifier,
        )
        expected = keyutils.KeySequence(
            QtCore.Qt.Key_0,
            QtCore.Qt.Key_1,
            QtCore.Qt.Key_A | QtCore.Qt.ControlModifier,
        )
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

    @pytest.mark.parametrize(
        'keystr, expected',
        [
            (
                '<Ctrl-Alt-y>',
                keyutils.KeySequence(
                    QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.Key_Y
                ),
            ),
            ('x', keyutils.KeySequence(QtCore.Qt.Key_X)),
            ('X', keyutils.KeySequence(QtCore.Qt.ShiftModifier | QtCore.Qt.Key_X)),
            ('<Escape>', keyutils.KeySequence(QtCore.Qt.Key_Escape)),
            (
                'xyz',
                keyutils.KeySequence(QtCore.Qt.Key_X, QtCore.Qt.Key_Y, QtCore.Qt.Key_Z),
            ),
            (
                '<Control-x><Meta-y>',
                keyutils.KeySequence(
                    QtCore.Qt.ControlModifier | QtCore.Qt.Key_X,
                    QtCore.Qt.MetaModifier | QtCore.Qt.Key_Y,
                ),
            ),
            (
                '<Shift-x>',
                keyutils.KeySequence(QtCore.Qt.ShiftModifier | QtCore.Qt.Key_X),
            ),
            ('<Alt-x>', keyutils.KeySequence(QtCore.Qt.AltModifier | QtCore.Qt.Key_X)),
            (
                '<Control-x>',
                keyutils.KeySequence(QtCore.Qt.ControlModifier | QtCore.Qt.Key_X),
            ),
            (
                '<Meta-x>',
                keyutils.KeySequence(QtCore.Qt.MetaModifier | QtCore.Qt.Key_X),
            ),
            (
                '<Num-x>',
                keyutils.KeySequence(QtCore.Qt.KeypadModifier | QtCore.Qt.Key_X),
            ),
            ('>', keyutils.KeySequence(QtCore.Qt.Key_Greater)),
            ('<', keyutils.KeySequence(QtCore.Qt.Key_Less)),
            ('a>', keyutils.KeySequence(QtCore.Qt.Key_A, QtCore.Qt.Key_Greater)),
            ('a<', keyutils.KeySequence(QtCore.Qt.Key_A, QtCore.Qt.Key_Less)),
            ('>a', keyutils.KeySequence(QtCore.Qt.Key_Greater, QtCore.Qt.Key_A)),
            ('<a', keyutils.KeySequence(QtCore.Qt.Key_Less, QtCore.Qt.Key_A)),
            (
                '<alt+greater>',
                keyutils.KeySequence(QtCore.Qt.Key_Greater | QtCore.Qt.AltModifier),
            ),
            (
                '<alt+less>',
                keyutils.KeySequence(QtCore.Qt.Key_Less | QtCore.Qt.AltModifier),
            ),
            ('<alt+<>', keyutils.KeyParseError),
            ('<alt+>>', keyutils.KeyParseError),
            ('<blub>', keyutils.KeyParseError),
            ('<>', keyutils.KeyParseError),
            ('\U00010000', keyutils.KeyParseError),
        ],
    )
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
    ev = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress, QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier, 'A'
    )
    info = keyutils.KeyInfo.from_event(ev)
    assert info.key == QtCore.Qt.Key_A
    assert info.modifiers == QtCore.Qt.ShiftModifier


def test_key_info_to_event():
    info = keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier)
    ev = info.to_event()
    assert ev.key() == QtCore.Qt.Key_A
    assert ev.modifiers() == QtCore.Qt.ShiftModifier
    assert ev.text() == 'A'


def test_key_info_to_int():
    info = keyutils.KeyInfo(QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier)
    assert info.to_int() == QtCore.Qt.Key_A | QtCore.Qt.ShiftModifier


@pytest.mark.parametrize(
    'key, printable',
    [
        (QtCore.Qt.Key_Control, False),
        (QtCore.Qt.Key_Escape, False),
        (QtCore.Qt.Key_Tab, False),
        (QtCore.Qt.Key_Backtab, False),
        (QtCore.Qt.Key_Backspace, False),
        (QtCore.Qt.Key_Return, False),
        (QtCore.Qt.Key_Enter, False),
        (QtCore.Qt.Key_Space, False),
        (0x0, False),  # Used by Qt for unknown keys
        (QtCore.Qt.Key_ydiaeresis, True),
        (QtCore.Qt.Key_X, True),
    ],
)
def test_is_printable(key, printable):
    assert keyutils._is_printable(key) == printable
    assert keyutils.is_special(key, QtCore.Qt.NoModifier) != printable


@pytest.mark.parametrize(
    'key, modifiers, special',
    [
        (QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier, True),
        (QtCore.Qt.Key_Escape, QtCore.Qt.ShiftModifier, True),
        (QtCore.Qt.Key_Escape, QtCore.Qt.ControlModifier, True),
        (QtCore.Qt.Key_X, QtCore.Qt.ControlModifier, True),
        (QtCore.Qt.Key_X, QtCore.Qt.NoModifier, False),
        (QtCore.Qt.Key_2, QtCore.Qt.KeypadModifier, True),
        (QtCore.Qt.Key_2, QtCore.Qt.NoModifier, False),
        (QtCore.Qt.Key_Shift, QtCore.Qt.ShiftModifier, True),
        (QtCore.Qt.Key_Control, QtCore.Qt.ControlModifier, True),
        (QtCore.Qt.Key_Alt, QtCore.Qt.AltModifier, True),
        (QtCore.Qt.Key_Meta, QtCore.Qt.MetaModifier, True),
        (QtCore.Qt.Key_Mode_switch, QtCore.Qt.GroupSwitchModifier, True),
    ],
)
def test_is_special(key, modifiers, special):
    assert keyutils.is_special(key, modifiers) == special


@pytest.mark.parametrize(
    'key, ismodifier',
    [
        (QtCore.Qt.Key_Control, True),
        (QtCore.Qt.Key_X, False),
        (QtCore.Qt.Key_Super_L, False),  # Modifier but not in _MODIFIER_MAP
    ],
)
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
        func(QtCore.Qt.Key_X | QtCore.Qt.ControlModifier)
