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

from qutebrowser.utils import utils
from qutebrowser.qt import QtGui, QtCore


# Map Qt::Key values to their Qt::KeyboardModifier value.
_MODIFIER_MAP = {
    QtCore.Qt.Key_Shift: QtCore.Qt.ShiftModifier,
    QtCore.Qt.Key_Control: QtCore.Qt.ControlModifier,
    QtCore.Qt.Key_Alt: QtCore.Qt.AltModifier,
    QtCore.Qt.Key_Meta: QtCore.Qt.MetaModifier,
    QtCore.Qt.Key_AltGr: QtCore.Qt.GroupSwitchModifier,
    QtCore.Qt.Key_Mode_switch: QtCore.Qt.GroupSwitchModifier,
}

_NIL_KEY = QtCore.Qt.Key(0)

_ModifierType = Union[QtCore.Qt.KeyboardModifier, QtCore.Qt.KeyboardModifiers]


_SPECIAL_NAMES = {
    # Some keys handled in a weird way by QKeySequence::toString.
    # See https://bugreports.qt.io/browse/QTBUG-40030
    # Most are unlikely to be ever needed, but you never know ;)
    # For dead/combining keys, we return the corresponding non-combining
    # key, as that's easier to add to the config.

    QtCore.Qt.Key_Super_L: 'Super L',
    QtCore.Qt.Key_Super_R: 'Super R',
    QtCore.Qt.Key_Hyper_L: 'Hyper L',
    QtCore.Qt.Key_Hyper_R: 'Hyper R',
    QtCore.Qt.Key_Direction_L: 'Direction L',
    QtCore.Qt.Key_Direction_R: 'Direction R',

    QtCore.Qt.Key_Shift: 'Shift',
    QtCore.Qt.Key_Control: 'Control',
    QtCore.Qt.Key_Meta: 'Meta',
    QtCore.Qt.Key_Alt: 'Alt',

    QtCore.Qt.Key_AltGr: 'AltGr',
    QtCore.Qt.Key_Multi_key: 'Multi key',
    QtCore.Qt.Key_SingleCandidate: 'Single Candidate',
    QtCore.Qt.Key_Mode_switch: 'Mode switch',
    QtCore.Qt.Key_Dead_Grave: '`',
    QtCore.Qt.Key_Dead_Acute: '´',
    QtCore.Qt.Key_Dead_Circumflex: '^',
    QtCore.Qt.Key_Dead_Tilde: '~',
    QtCore.Qt.Key_Dead_Macron: '¯',
    QtCore.Qt.Key_Dead_Breve: '˘',
    QtCore.Qt.Key_Dead_Abovedot: '˙',
    QtCore.Qt.Key_Dead_Diaeresis: '¨',
    QtCore.Qt.Key_Dead_Abovering: '˚',
    QtCore.Qt.Key_Dead_Doubleacute: '˝',
    QtCore.Qt.Key_Dead_Caron: 'ˇ',
    QtCore.Qt.Key_Dead_Cedilla: '¸',
    QtCore.Qt.Key_Dead_Ogonek: '˛',
    QtCore.Qt.Key_Dead_Iota: 'Iota',
    QtCore.Qt.Key_Dead_Voiced_Sound: 'Voiced Sound',
    QtCore.Qt.Key_Dead_Semivoiced_Sound: 'Semivoiced Sound',
    QtCore.Qt.Key_Dead_Belowdot: 'Belowdot',
    QtCore.Qt.Key_Dead_Hook: 'Hook',
    QtCore.Qt.Key_Dead_Horn: 'Horn',

    QtCore.Qt.Key_Dead_Stroke: '\u0335',  # '̵'
    QtCore.Qt.Key_Dead_Abovecomma: '\u0313',  # '̓'
    QtCore.Qt.Key_Dead_Abovereversedcomma: '\u0314',  # '̔'
    QtCore.Qt.Key_Dead_Doublegrave: '\u030f',  # '̏'
    QtCore.Qt.Key_Dead_Belowring: '\u0325',  # '̥'
    QtCore.Qt.Key_Dead_Belowmacron: '\u0331',  # '̱'
    QtCore.Qt.Key_Dead_Belowcircumflex: '\u032d',  # '̭'
    QtCore.Qt.Key_Dead_Belowtilde: '\u0330',  # '̰'
    QtCore.Qt.Key_Dead_Belowbreve: '\u032e',  # '̮'
    QtCore.Qt.Key_Dead_Belowdiaeresis: '\u0324',  # '̤'
    QtCore.Qt.Key_Dead_Invertedbreve: '\u0311',  # '̑'
    QtCore.Qt.Key_Dead_Belowcomma: '\u0326',  # '̦'
    QtCore.Qt.Key_Dead_Currency: '¤',
    QtCore.Qt.Key_Dead_a: 'a',
    QtCore.Qt.Key_Dead_A: 'A',
    QtCore.Qt.Key_Dead_e: 'e',
    QtCore.Qt.Key_Dead_E: 'E',
    QtCore.Qt.Key_Dead_i: 'i',
    QtCore.Qt.Key_Dead_I: 'I',
    QtCore.Qt.Key_Dead_o: 'o',
    QtCore.Qt.Key_Dead_O: 'O',
    QtCore.Qt.Key_Dead_u: 'u',
    QtCore.Qt.Key_Dead_U: 'U',
    QtCore.Qt.Key_Dead_Small_Schwa: 'ə',
    QtCore.Qt.Key_Dead_Capital_Schwa: 'Ə',
    QtCore.Qt.Key_Dead_Greek: 'Greek',
    QtCore.Qt.Key_Dead_Lowline: '\u0332',  # '̲'
    QtCore.Qt.Key_Dead_Aboveverticalline: '\u030d',  # '̍'
    QtCore.Qt.Key_Dead_Belowverticalline: '\u0329',
    QtCore.Qt.Key_Dead_Longsolidusoverlay: '\u0338',  # '̸'

    QtCore.Qt.Key_Memo: 'Memo',
    QtCore.Qt.Key_ToDoList: 'To Do List',
    QtCore.Qt.Key_Calendar: 'Calendar',
    QtCore.Qt.Key_ContrastAdjust: 'Contrast Adjust',
    QtCore.Qt.Key_LaunchG: 'Launch (G)',
    QtCore.Qt.Key_LaunchH: 'Launch (H)',

    QtCore.Qt.Key_MediaLast: 'Media Last',

    QtCore.Qt.Key_unknown: 'Unknown',

    # For some keys, we just want a different name
    QtCore.Qt.Key_Escape: 'Escape',

    _NIL_KEY: 'nil',
}


def _assert_plain_key(key: QtCore.Qt.Key) -> None:
    """Make sure this is a key without KeyboardModifiers mixed in."""
    assert not key & QtCore.Qt.KeyboardModifierMask, hex(key)


def _assert_plain_modifier(key: _ModifierType) -> None:
    """Make sure this is a modifier without a key mixed in."""
    mask = QtCore.Qt.KeyboardModifierMask
    assert not key & ~mask, hex(key)  # type: ignore[operator]


def _is_printable(key: QtCore.Qt.Key) -> bool:
    _assert_plain_key(key)
    return key <= 0xFF and key not in [QtCore.Qt.Key_Space, _NIL_KEY]


def is_special(key: QtCore.Qt.Key, modifiers: _ModifierType) -> bool:
    """Check whether this key requires special key syntax."""
    _assert_plain_key(key)
    _assert_plain_modifier(modifiers)
    return not (
        _is_printable(key)
        and modifiers in [QtCore.Qt.ShiftModifier, QtCore.Qt.NoModifier]
    )


def is_modifier_key(key: QtCore.Qt.Key) -> bool:
    """Test whether the given key is a modifier.

    This only considers keys which are part of Qt::KeyboardModifiers, i.e.
    which would interrupt a key chain like "yY" when handled.
    """
    _assert_plain_key(key)
    return key in _MODIFIER_MAP


def _is_surrogate(key: QtCore.Qt.Key) -> bool:
    """Check if a codepoint is a UTF-16 surrogate.

    UTF-16 surrogates are a reserved range of Unicode from 0xd800
    to 0xd8ff, used to encode Unicode codepoints above the BMP
    (Base Multilingual Plane).
    """
    _assert_plain_key(key)
    return 0xd800 <= key <= 0xdfff


def _remap_unicode(key: QtCore.Qt.Key, text: str) -> QtCore.Qt.Key:
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
        return QtCore.Qt.Key(ord(text[0]))
    return key


def _check_valid_utf8(s: str, data: Union[QtCore.Qt.Key, _ModifierType]) -> None:
    """Make sure the given string is valid UTF-8.

    Makes sure there are no chars where Qt did fall back to weird UTF-16
    surrogates.
    """
    try:
        s.encode('utf-8')
    except UnicodeEncodeError as e:  # pragma: no cover
        raise ValueError("Invalid encoding in 0x{:x} -> {}: {}"
                         .format(int(data), s, e))


def _key_to_string(key: QtCore.Qt.Key) -> str:
    """Convert a Qt::Key member to a meaningful name.

    Args:
        key: A Qt::Key member.

    Return:
        A name of the key as a string.
    """
    _assert_plain_key(key)

    if key in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[key]

    result = QtGui.QKeySequence(key).toString()
    _check_valid_utf8(result, key)
    return result


def _modifiers_to_string(modifiers: _ModifierType) -> str:
    """Convert the given Qt::KeyboardModifiers to a string.

    Handles Qt.GroupSwitchModifier because Qt doesn't handle that as a
    modifier.
    """
    _assert_plain_modifier(modifiers)
    altgr = QtCore.Qt.GroupSwitchModifier
    if modifiers & altgr:  # type: ignore[operator]
        modifiers &= ~altgr  # type: ignore[operator, assignment]
        result = 'AltGr+'
    else:
        result = ''

    result += QtGui.QKeySequence(modifiers).toString()

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

    key: QtCore.Qt.Key
    modifiers: _ModifierType

    @classmethod
    def from_event(cls, e: QtGui.QKeyEvent) -> 'KeyInfo':
        """Get a KeyInfo object from a QKeyEvent.

        This makes sure that key/modifiers are never mixed and also remaps
        UTF-16 surrogates to work around QTBUG-72776.
        """
        key = _remap_unicode(QtCore.Qt.Key(e.key()), e.text())
        modifiers = e.modifiers()
        _assert_plain_key(key)
        _assert_plain_modifier(modifiers)
        return cls(key, cast(QtCore.Qt.KeyboardModifier, modifiers))

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
            if self.modifiers == QtCore.Qt.ShiftModifier:
                assert not is_special(self.key, self.modifiers)
                return key_string.upper()
            elif self.modifiers == QtCore.Qt.NoModifier:
                assert not is_special(self.key, self.modifiers)
                return key_string.lower()
            else:
                # Use special binding syntax, but <Ctrl-a> instead of <Ctrl-A>
                key_string = key_string.lower()

        modifiers = QtCore.Qt.KeyboardModifier(modifiers)

        # "special" binding
        assert is_special(self.key, self.modifiers)
        modifier_string = _modifiers_to_string(modifiers)
        return '<{}{}>'.format(modifier_string, key_string)

    def text(self) -> str:
        """Get the text which would be displayed when pressing this key."""
        control = {
            QtCore.Qt.Key_Space: ' ',
            QtCore.Qt.Key_Tab: '\t',
            QtCore.Qt.Key_Backspace: '\b',
            QtCore.Qt.Key_Return: '\r',
            QtCore.Qt.Key_Enter: '\r',
            QtCore.Qt.Key_Escape: '\x1b',
        }

        if self.key in control:
            return control[self.key]
        elif not _is_printable(self.key):
            return ''

        text = QtGui.QKeySequence(self.key).toString()
        if not self.modifiers & QtCore.Qt.ShiftModifier:  # type: ignore[operator]
            text = text.lower()
        return text

    def to_event(
        self, typ: QtCore.QEvent.Type = QtCore.QEvent.KeyPress
    ) -> QtGui.QKeyEvent:
        """Get a QKeyEvent from this KeyInfo."""
        return QtGui.QKeyEvent(typ, self.key, self.modifiers, self.text())

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
        self._sequences: List[QtGui.QKeySequence] = []
        for sub in utils.chunk(keys, self._MAX_LEN):
            args = [self._convert_key(key) for key in sub]
            sequence = QtGui.QKeySequence(*args)
            self._sequences.append(sequence)
        if keys:
            assert self
        self._validate()

    def _convert_key(self, key: Union[int, QtCore.Qt.KeyboardModifiers]) -> int:
        """Convert a single key for QKeySequence."""
        assert isinstance(key, (int, QtCore.Qt.KeyboardModifiers)), key
        return int(key)

    def __str__(self) -> str:
        parts = []
        for info in self:
            parts.append(str(info))
        return ''.join(parts)

    def __iter__(self) -> Iterator[KeyInfo]:
        """Iterate over KeyInfo objects."""
        for key_and_modifiers in self._iter_keys():
            key = QtCore.Qt.Key(
                int(key_and_modifiers) & ~QtCore.Qt.KeyboardModifierMask
            )
            modifiers = QtCore.Qt.KeyboardModifiers(  # type: ignore[call-overload]
                int(key_and_modifiers) & QtCore.Qt.KeyboardModifierMask
            )
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
            if info.key < QtCore.Qt.Key_Space or info.key >= QtCore.Qt.Key_unknown:
                raise KeyParseError(keystr, "Got invalid key!")

        for seq in self._sequences:
            if not seq:
                raise KeyParseError(keystr, "Got invalid key!")

    def matches(self, other: 'KeySequence') -> QtGui.QKeySequence.SequenceMatch:
        """Check whether the given KeySequence matches with this one.

        We store multiple QKeySequences with <= 4 keys each, so we need to
        match those pair-wise, and account for an unequal amount of sequences
        as well.
        """
        # pylint: disable=protected-access

        if len(self._sequences) > len(other._sequences):
            # If we entered more sequences than there are in the config,
            # there's no way there can be a match.
            return QtGui.QKeySequence.NoMatch

        for entered, configured in zip(self._sequences, other._sequences):
            # If we get NoMatch/PartialMatch in a sequence, we can abort there.
            match = entered.matches(configured)
            if match != QtGui.QKeySequence.ExactMatch:
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
            return QtGui.QKeySequence.ExactMatch
        elif len(self._sequences) < len(other._sequences):
            return QtGui.QKeySequence.PartialMatch
        else:
            raise utils.Unreachable("self={!r} other={!r}".format(self, other))

    def append_event(self, ev: QtGui.QKeyEvent) -> 'KeySequence':
        """Create a new KeySequence object with the given QKeyEvent added."""
        key = QtCore.Qt.Key(ev.key())

        _assert_plain_key(key)
        _assert_plain_modifier(ev.modifiers())

        key = _remap_unicode(key, ev.text())
        modifiers = int(ev.modifiers())

        if key == _NIL_KEY:
            raise KeyParseError(None, "Got nil key!")

        # We always remove Qt.GroupSwitchModifier because QKeySequence has no
        # way to mention that in a binding anyways...
        modifiers &= ~QtCore.Qt.GroupSwitchModifier

        # We change Qt.Key_Backtab to Key_Tab here because nobody would
        # configure "Shift-Backtab" in their config.
        if modifiers & QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Backtab:
            key = QtCore.Qt.Key_Tab

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
        if (
            modifiers == QtCore.Qt.ShiftModifier
            and _is_printable(key)
            and not ev.text().isupper()
        ):
            modifiers = QtCore.Qt.KeyboardModifiers()  # type: ignore[assignment]

        # On macOS, swap Ctrl and Meta back
        #
        # We don't use Qt.AA_MacDontSwapCtrlAndMeta because that also affects
        # Qt/QtWebEngine's own shortcuts. However, we do want "Ctrl" and "Meta"
        # (or "Cmd") in a key binding name to actually represent what's on the
        # keyboard.
        if utils.is_mac:
            if (
                modifiers & QtCore.Qt.ControlModifier
                and modifiers & QtCore.Qt.MetaModifier
            ):
                pass
            elif modifiers & QtCore.Qt.ControlModifier:
                modifiers &= ~QtCore.Qt.ControlModifier
                modifiers |= QtCore.Qt.MetaModifier
            elif modifiers & QtCore.Qt.MetaModifier:
                modifiers &= ~QtCore.Qt.MetaModifier
                modifiers |= QtCore.Qt.ControlModifier

        keys = list(self._iter_keys())
        keys.append(key | int(modifiers))

        return self.__class__(*keys)

    def strip_modifiers(self) -> 'KeySequence':
        """Strip optional modifiers from keys."""
        modifiers = QtCore.Qt.KeypadModifier
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
        new = cls()
        strings = list(_parse_keystring(keystr))
        for sub in utils.chunk(strings, cls._MAX_LEN):
            sequence = QtGui.QKeySequence(', '.join(sub))
            new._sequences.append(sequence)

        if keystr:
            assert new, keystr

        new._validate(keystr)
        return new
