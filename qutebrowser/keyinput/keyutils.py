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

"""Our own QKeySequence-like class and related utilities.

Note that Qt's type safety (or rather, lack thereof) is somewhat scary when it
comes to keys/modifiers. Many places (such as QKeyEvent::key()) don't actually
return a Qt::Key, they return an int.

To make things worse, when talking about a "key", sometimes Qt means a Qt::Key
member. However, sometimes it means a Qt::Key member ORed with
Qt.KeyboardModifiers...

Because of that, _assert_plain_key() and _assert_plain_modifier() make sure we
handle what we actually think we do.
"""

import itertools
import dataclasses
from typing import cast, overload, Iterable, Iterator, List, Mapping, Optional, Union

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeySequence, QKeyEvent

from qutebrowser.utils import utils


# Map Qt::Key values to their Qt::KeyboardModifier value.
_MODIFIER_MAP = {
    Qt.Key_Shift: Qt.ShiftModifier,
    Qt.Key_Control: Qt.ControlModifier,
    Qt.Key_Alt: Qt.AltModifier,
    Qt.Key_Meta: Qt.MetaModifier,
    Qt.Key_AltGr: Qt.GroupSwitchModifier,
    Qt.Key_Mode_switch: Qt.GroupSwitchModifier,
}

_NIL_KEY = Qt.Key(0)

_ModifierType = Union[Qt.KeyboardModifier, Qt.KeyboardModifiers]


_SPECIAL_NAMES = {
    # Some keys handled in a weird way by QKeySequence::toString.
    # See https://bugreports.qt.io/browse/QTBUG-40030
    # Most are unlikely to be ever needed, but you never know ;)
    # For dead/combining keys, we return the corresponding non-combining
    # key, as that's easier to add to the config.

    Qt.Key_Super_L: 'Super L',
    Qt.Key_Super_R: 'Super R',
    Qt.Key_Hyper_L: 'Hyper L',
    Qt.Key_Hyper_R: 'Hyper R',
    Qt.Key_Direction_L: 'Direction L',
    Qt.Key_Direction_R: 'Direction R',

    Qt.Key_Shift: 'Shift',
    Qt.Key_Control: 'Control',
    Qt.Key_Meta: 'Meta',
    Qt.Key_Alt: 'Alt',

    Qt.Key_AltGr: 'AltGr',
    Qt.Key_Multi_key: 'Multi key',
    Qt.Key_SingleCandidate: 'Single Candidate',
    Qt.Key_Mode_switch: 'Mode switch',
    Qt.Key_Dead_Grave: '`',
    Qt.Key_Dead_Acute: '´',
    Qt.Key_Dead_Circumflex: '^',
    Qt.Key_Dead_Tilde: '~',
    Qt.Key_Dead_Macron: '¯',
    Qt.Key_Dead_Breve: '˘',
    Qt.Key_Dead_Abovedot: '˙',
    Qt.Key_Dead_Diaeresis: '¨',
    Qt.Key_Dead_Abovering: '˚',
    Qt.Key_Dead_Doubleacute: '˝',
    Qt.Key_Dead_Caron: 'ˇ',
    Qt.Key_Dead_Cedilla: '¸',
    Qt.Key_Dead_Ogonek: '˛',
    Qt.Key_Dead_Iota: 'Iota',
    Qt.Key_Dead_Voiced_Sound: 'Voiced Sound',
    Qt.Key_Dead_Semivoiced_Sound: 'Semivoiced Sound',
    Qt.Key_Dead_Belowdot: 'Belowdot',
    Qt.Key_Dead_Hook: 'Hook',
    Qt.Key_Dead_Horn: 'Horn',

    Qt.Key_Dead_Stroke: '\u0335',  # '̵'
    Qt.Key_Dead_Abovecomma: '\u0313',  # '̓'
    Qt.Key_Dead_Abovereversedcomma: '\u0314',  # '̔'
    Qt.Key_Dead_Doublegrave: '\u030f',  # '̏'
    Qt.Key_Dead_Belowring: '\u0325',  # '̥'
    Qt.Key_Dead_Belowmacron: '\u0331',  # '̱'
    Qt.Key_Dead_Belowcircumflex: '\u032d',  # '̭'
    Qt.Key_Dead_Belowtilde: '\u0330',  # '̰'
    Qt.Key_Dead_Belowbreve: '\u032e',  # '̮'
    Qt.Key_Dead_Belowdiaeresis: '\u0324',  # '̤'
    Qt.Key_Dead_Invertedbreve: '\u0311',  # '̑'
    Qt.Key_Dead_Belowcomma: '\u0326',  # '̦'
    Qt.Key_Dead_Currency: '¤',
    Qt.Key_Dead_a: 'a',
    Qt.Key_Dead_A: 'A',
    Qt.Key_Dead_e: 'e',
    Qt.Key_Dead_E: 'E',
    Qt.Key_Dead_i: 'i',
    Qt.Key_Dead_I: 'I',
    Qt.Key_Dead_o: 'o',
    Qt.Key_Dead_O: 'O',
    Qt.Key_Dead_u: 'u',
    Qt.Key_Dead_U: 'U',
    Qt.Key_Dead_Small_Schwa: 'ə',
    Qt.Key_Dead_Capital_Schwa: 'Ə',
    Qt.Key_Dead_Greek: 'Greek',
    Qt.Key_Dead_Lowline: '\u0332',  # '̲'
    Qt.Key_Dead_Aboveverticalline: '\u030d',  # '̍'
    Qt.Key_Dead_Belowverticalline: '\u0329',
    Qt.Key_Dead_Longsolidusoverlay: '\u0338',  # '̸'

    Qt.Key_Memo: 'Memo',
    Qt.Key_ToDoList: 'To Do List',
    Qt.Key_Calendar: 'Calendar',
    Qt.Key_ContrastAdjust: 'Contrast Adjust',
    Qt.Key_LaunchG: 'Launch (G)',
    Qt.Key_LaunchH: 'Launch (H)',

    Qt.Key_MediaLast: 'Media Last',

    Qt.Key_unknown: 'Unknown',

    # For some keys, we just want a different name
    Qt.Key_Escape: 'Escape',

    _NIL_KEY: 'nil',
}


def _assert_plain_key(key: Qt.Key) -> None:
    """Make sure this is a key without KeyboardModifiers mixed in."""
    assert not key & Qt.KeyboardModifierMask, hex(key)


def _assert_plain_modifier(key: _ModifierType) -> None:
    """Make sure this is a modifier without a key mixed in."""
    mask = Qt.KeyboardModifierMask
    assert not key & ~mask, hex(key)  # type: ignore[operator]


def _is_printable(key: Qt.Key) -> bool:
    _assert_plain_key(key)
    return key <= 0xff and key not in [Qt.Key_Space, _NIL_KEY]


def is_special(key: Qt.Key, modifiers: _ModifierType) -> bool:
    """Check whether this key requires special key syntax."""
    _assert_plain_key(key)
    _assert_plain_modifier(modifiers)
    return not (_is_printable(key) and
                modifiers in [Qt.ShiftModifier, Qt.NoModifier])


def is_modifier_key(key: Qt.Key) -> bool:
    """Test whether the given key is a modifier.

    This only considers keys which are part of Qt::KeyboardModifiers, i.e.
    which would interrupt a key chain like "yY" when handled.
    """
    _assert_plain_key(key)
    return key in _MODIFIER_MAP


def _is_surrogate(key: Qt.Key) -> bool:
    """Check if a codepoint is a UTF-16 surrogate.

    UTF-16 surrogates are a reserved range of Unicode from 0xd800
    to 0xd8ff, used to encode Unicode codepoints above the BMP
    (Base Multilingual Plane).
    """
    _assert_plain_key(key)
    return 0xd800 <= key <= 0xdfff


def _remap_unicode(key: Qt.Key, text: str) -> Qt.Key:
    """Work around QtKeyEvent's bad values for high codepoints.

    QKeyEvent handles higher unicode codepoints poorly. It uses UTF-16 to
    handle key events, and for higher codepoints that require UTF-16 surrogates
    (e.g. emoji and some CJK characters), it sets the keycode to just the upper
    half of the surrogate, which renders it useless, and breaks UTF-8 encoding,
    causing crashes. So we detect this case, and reassign the key code to be
    the full Unicode codepoint, which we can recover from the text() property,
    which has the full character.

    This is a WORKAROUND for https://bugreports.qt.io/browse/QTBUG-72776.
    """
    _assert_plain_key(key)
    if _is_surrogate(key):
        if len(text) != 1:
            raise KeyParseError(text, "Expected 1 character for surrogate, "
                                "but got {}!".format(len(text)))
        return Qt.Key(ord(text[0]))
    return key


def _check_valid_utf8(s: str, data: Union[Qt.Key, _ModifierType]) -> None:
    """Make sure the given string is valid UTF-8.

    Makes sure there are no chars where Qt did fall back to weird UTF-16
    surrogates.
    """
    try:
        s.encode('utf-8')
    except UnicodeEncodeError as e:  # pragma: no cover
        raise ValueError("Invalid encoding in 0x{:x} -> {}: {}"
                         .format(int(data), s, e))


def _key_to_string(key: Qt.Key) -> str:
    """Convert a Qt::Key member to a meaningful name.

    Args:
        key: A Qt::Key member.

    Return:
        A name of the key as a string.
    """
    _assert_plain_key(key)

    if key in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[key]

    result = QKeySequence(key).toString()
    _check_valid_utf8(result, key)
    return result


def _modifiers_to_string(modifiers: _ModifierType) -> str:
    """Convert the given Qt::KeyboardModifiers to a string.

    Handles Qt.GroupSwitchModifier because Qt doesn't handle that as a
    modifier.
    """
    _assert_plain_modifier(modifiers)
    altgr = Qt.GroupSwitchModifier
    if modifiers & altgr:  # type: ignore[operator]
        modifiers &= ~altgr  # type: ignore[operator, assignment]
        result = 'AltGr+'
    else:
        result = ''

    result += QKeySequence(modifiers).toString()

    _check_valid_utf8(result, modifiers)
    return result


class KeyParseError(Exception):

    """Raised by _parse_single_key/parse_keystring on parse errors."""

    def __init__(self, keystr: Optional[str], error: str) -> None:
        if keystr is None:
            msg = "Could not parse keystring: {}".format(error)
        else:
            msg = "Could not parse {!r}: {}".format(keystr, error)
        super().__init__(msg)


def _parse_keystring(keystr: str) -> Iterator[str]:
    key = ''
    special = False
    for c in keystr:
        if c == '>':
            if special:
                yield _parse_special_key(key)
                key = ''
                special = False
            else:
                yield '>'
                assert not key, key
        elif c == '<':
            special = True
        elif special:
            key += c
        else:
            yield _parse_single_key(c)
    if special:
        yield '<'
        for c in key:
            yield _parse_single_key(c)


def _parse_special_key(keystr: str) -> str:
    """Normalize a keystring like Ctrl-Q to a keystring like Ctrl+Q.

    Args:
        keystr: The key combination as a string.

    Return:
        The normalized keystring.
    """
    keystr = keystr.lower()
    replacements = (
        ('control', 'ctrl'),
        ('windows', 'meta'),
        ('mod4', 'meta'),
        ('command', 'meta'),
        ('cmd', 'meta'),
        ('super', 'meta'),
        ('mod1', 'alt'),
        ('less', '<'),
        ('greater', '>'),
    )
    for (orig, repl) in replacements:
        keystr = keystr.replace(orig, repl)

    for mod in ['ctrl', 'meta', 'alt', 'shift', 'num']:
        keystr = keystr.replace(mod + '-', mod + '+')
    return keystr


def _parse_single_key(keystr: str) -> str:
    """Get a keystring for QKeySequence for a single key."""
    return 'Shift+' + keystr if keystr.isupper() else keystr


@dataclasses.dataclass(frozen=True, order=True)
class KeyInfo:

    """A key with optional modifiers.

    Attributes:
        key: A Qt::Key member.
        modifiers: A Qt::KeyboardModifiers enum value.
    """

    key: Qt.Key
    modifiers: _ModifierType

    @classmethod
    def from_event(cls, e: QKeyEvent) -> 'KeyInfo':
        """Get a KeyInfo object from a QKeyEvent.

        This makes sure that key/modifiers are never mixed and also remaps
        UTF-16 surrogates to work around QTBUG-72776.
        """
        key = _remap_unicode(Qt.Key(e.key()), e.text())
        modifiers = e.modifiers()
        _assert_plain_key(key)
        _assert_plain_modifier(modifiers)
        return cls(key, cast(Qt.KeyboardModifier, modifiers))

    def __str__(self) -> str:
        """Convert this KeyInfo to a meaningful name.

        Return:
            A name of the key (combination) as a string.
        """
        key_string = _key_to_string(self.key)
        modifiers = int(self.modifiers)

        if self.key in _MODIFIER_MAP:
            # Don't return e.g. <Shift+Shift>
            modifiers &= ~_MODIFIER_MAP[self.key]
        elif _is_printable(self.key):
            # "normal" binding
            if not key_string:  # pragma: no cover
                raise ValueError("Got empty string for key 0x{:x}!"
                                 .format(self.key))

            assert len(key_string) == 1, key_string
            if self.modifiers == Qt.ShiftModifier:
                assert not is_special(self.key, self.modifiers)
                return key_string.upper()
            elif self.modifiers == Qt.NoModifier:
                assert not is_special(self.key, self.modifiers)
                return key_string.lower()
            else:
                # Use special binding syntax, but <Ctrl-a> instead of <Ctrl-A>
                key_string = key_string.lower()

        modifiers = Qt.KeyboardModifier(modifiers)

        # "special" binding
        assert is_special(self.key, self.modifiers)
        modifier_string = _modifiers_to_string(modifiers)
        return '<{}{}>'.format(modifier_string, key_string)

    def text(self) -> str:
        """Get the text which would be displayed when pressing this key."""
        control = {
            Qt.Key_Space: ' ',
            Qt.Key_Tab: '\t',
            Qt.Key_Backspace: '\b',
            Qt.Key_Return: '\r',
            Qt.Key_Enter: '\r',
            Qt.Key_Escape: '\x1b',
        }

        if self.key in control:
            return control[self.key]
        elif not _is_printable(self.key):
            return ''

        text = QKeySequence(self.key).toString()
        if not self.modifiers & Qt.ShiftModifier:  # type: ignore[operator]
            text = text.lower()
        return text

    def to_event(self, typ: QEvent.Type = QEvent.KeyPress) -> QKeyEvent:
        """Get a QKeyEvent from this KeyInfo."""
        return QKeyEvent(typ, self.key, self.modifiers, self.text())

    def to_int(self) -> int:
        """Get the key as an integer (with key/modifiers)."""
        return int(self.key) | int(self.modifiers)


class KeySequence:

    """A sequence of key presses.

    This internally uses chained QKeySequence objects and exposes a nicer
    interface over it.

    NOTE: While private members of this class are in theory mutable, they must
    not be mutated in order to ensure consistent hashing.

    Attributes:
        _sequences: A list of QKeySequence

    Class attributes:
        _MAX_LEN: The maximum amount of keys in a QKeySequence.
    """

    _MAX_LEN = 4

    def __init__(self, *keys: int) -> None:
        self._sequences: List[QKeySequence] = []
        for sub in utils.chunk(keys, self._MAX_LEN):
            args = [self._convert_key(key) for key in sub]
            sequence = QKeySequence(*args)
            self._sequences.append(sequence)
        if keys:
            assert self
        self._validate()

    def _convert_key(self, key: Qt.Key) -> int:
        """Convert a single key for QKeySequence."""
        assert isinstance(key, (int, Qt.KeyboardModifiers)), key
        return int(key)

    def __str__(self) -> str:
        parts = []
        for info in self:
            parts.append(str(info))
        return ''.join(parts)

    def __iter__(self) -> Iterator[KeyInfo]:
        """Iterate over KeyInfo objects."""
        for key_and_modifiers in self._iter_keys():
            key = Qt.Key(int(key_and_modifiers) & ~Qt.KeyboardModifierMask)
            modifiers = Qt.KeyboardModifiers(  # type: ignore[call-overload]
                int(key_and_modifiers) & Qt.KeyboardModifierMask)
            yield KeyInfo(key=key, modifiers=modifiers)

    def __repr__(self) -> str:
        return utils.get_repr(self, keys=str(self))

    def __lt__(self, other: 'KeySequence') -> bool:
        return self._sequences < other._sequences

    def __gt__(self, other: 'KeySequence') -> bool:
        return self._sequences > other._sequences

    def __le__(self, other: 'KeySequence') -> bool:
        return self._sequences <= other._sequences

    def __ge__(self, other: 'KeySequence') -> bool:
        return self._sequences >= other._sequences

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KeySequence):
            return NotImplemented
        return self._sequences == other._sequences

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, KeySequence):
            return NotImplemented
        return self._sequences != other._sequences

    def __hash__(self) -> int:
        return hash(tuple(self._sequences))

    def __len__(self) -> int:
        return sum(len(seq) for seq in self._sequences)

    def __bool__(self) -> bool:
        return bool(self._sequences)

    @overload
    def __getitem__(self, item: int) -> KeyInfo:
        ...

    @overload
    def __getitem__(self, item: slice) -> 'KeySequence':
        ...

    def __getitem__(self, item: Union[int, slice]) -> Union[KeyInfo, 'KeySequence']:
        if isinstance(item, slice):
            keys = list(self._iter_keys())
            return self.__class__(*keys[item])
        else:
            infos = list(self)
            return infos[item]

    def _iter_keys(self) -> Iterator[int]:
        sequences = cast(Iterable[Iterable[int]], self._sequences)
        return itertools.chain.from_iterable(sequences)

    def _validate(self, keystr: str = None) -> None:
        for info in self:
            if info.key < Qt.Key_Space or info.key >= Qt.Key_unknown:
                raise KeyParseError(keystr, "Got invalid key!")

        for seq in self._sequences:
            if not seq:
                raise KeyParseError(keystr, "Got invalid key!")

    def matches(self, other: 'KeySequence') -> QKeySequence.SequenceMatch:
        """Check whether the given KeySequence matches with this one.

        We store multiple QKeySequences with <= 4 keys each, so we need to
        match those pair-wise, and account for an unequal amount of sequences
        as well.
        """
        # pylint: disable=protected-access

        if len(self._sequences) > len(other._sequences):
            # If we entered more sequences than there are in the config,
            # there's no way there can be a match.
            return QKeySequence.NoMatch

        for entered, configured in zip(self._sequences, other._sequences):
            # If we get NoMatch/PartialMatch in a sequence, we can abort there.
            match = entered.matches(configured)
            if match != QKeySequence.ExactMatch:
                return match

        # We checked all common sequences and they had an ExactMatch.
        #
        # If there's still more sequences configured than entered, that's a
        # PartialMatch, as more keypresses can still follow and new sequences
        # will appear which we didn't check above.
        #
        # If there's the same amount of sequences configured and entered,
        # that's an EqualMatch.
        if len(self._sequences) == len(other._sequences):
            return QKeySequence.ExactMatch
        elif len(self._sequences) < len(other._sequences):
            return QKeySequence.PartialMatch
        else:
            raise utils.Unreachable("self={!r} other={!r}".format(self, other))

    def append_event(self, ev: QKeyEvent) -> 'KeySequence':
        """Create a new KeySequence object with the given QKeyEvent added."""
        key = Qt.Key(ev.key())

        _assert_plain_key(key)
        _assert_plain_modifier(ev.modifiers())

        key = _remap_unicode(key, ev.text())
        modifiers = int(ev.modifiers())

        if key == _NIL_KEY:
            raise KeyParseError(None, "Got nil key!")

        # We always remove Qt.GroupSwitchModifier because QKeySequence has no
        # way to mention that in a binding anyways...
        modifiers &= ~Qt.GroupSwitchModifier

        # We change Qt.Key_Backtab to Key_Tab here because nobody would
        # configure "Shift-Backtab" in their config.
        if modifiers & Qt.ShiftModifier and key == Qt.Key_Backtab:
            key = Qt.Key_Tab

        # We don't care about a shift modifier with symbols (Shift-: should
        # match a : binding even though we typed it with a shift on an
        # US-keyboard)
        #
        # However, we *do* care about Shift being involved if we got an
        # upper-case letter, as Shift-A should match a Shift-A binding, but not
        # an "a" binding.
        #
        # In addition, Shift also *is* relevant when other modifiers are
        # involved. Shift-Ctrl-X should not be equivalent to Ctrl-X.
        if (modifiers == Qt.ShiftModifier and
                _is_printable(key) and
                not ev.text().isupper()):
            modifiers = Qt.KeyboardModifiers()  # type: ignore[assignment]

        # On macOS, swap Ctrl and Meta back
        #
        # We don't use Qt.AA_MacDontSwapCtrlAndMeta because that also affects
        # Qt/QtWebEngine's own shortcuts. However, we do want "Ctrl" and "Meta"
        # (or "Cmd") in a key binding name to actually represent what's on the
        # keyboard.
        if utils.is_mac:
            if modifiers & Qt.ControlModifier and modifiers & Qt.MetaModifier:
                pass
            elif modifiers & Qt.ControlModifier:
                modifiers &= ~Qt.ControlModifier
                modifiers |= Qt.MetaModifier
            elif modifiers & Qt.MetaModifier:
                modifiers &= ~Qt.MetaModifier
                modifiers |= Qt.ControlModifier

        keys = list(self._iter_keys())
        keys.append(key | int(modifiers))

        return self.__class__(*keys)

    def strip_modifiers(self) -> 'KeySequence':
        """Strip optional modifiers from keys."""
        modifiers = Qt.KeypadModifier
        keys = [key & ~modifiers for key in self._iter_keys()]
        return self.__class__(*keys)

    def with_mappings(
            self,
            mappings: Mapping['KeySequence', 'KeySequence']
    ) -> 'KeySequence':
        """Get a new KeySequence with the given mappings applied."""
        keys = []
        for key in self._iter_keys():
            key_seq = KeySequence(key)
            if key_seq in mappings:
                keys += [info.to_int() for info in mappings[key_seq]]
            else:
                keys.append(key)
        return self.__class__(*keys)

    @classmethod
    def parse(cls, keystr: str) -> 'KeySequence':
        """Parse a keystring like <Ctrl-x> or xyz and return a KeySequence."""
        # pylint: disable=protected-access
        new = cls()
        strings = list(_parse_keystring(keystr))
        for sub in utils.chunk(strings, cls._MAX_LEN):
            sequence = QKeySequence(', '.join(sub))
            new._sequences.append(sequence)

        if keystr:
            assert new, keystr

        # pylint: disable=protected-access
        new._validate(keystr)
        return new
