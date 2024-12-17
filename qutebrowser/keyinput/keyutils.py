# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Our own QKeySequence-like class and related utilities.

Note that Qt's type safety (or rather, lack thereof) is somewhat scary when it
comes to keys/modifiers. Many places (such as QKeyEvent::key()) don't actually
return a Qt::Key, they return an int.

To make things worse, when talking about a "key", sometimes Qt means a Qt::Key
member. However, sometimes it means a Qt::Key member ORed with a
Qt.KeyboardModifier...

Because of that, _assert_plain_key() and _assert_plain_modifier() make sure we
handle what we actually think we do.
"""

import itertools
import dataclasses
from typing import Optional, Union, overload, cast
from collections.abc import Iterator, Iterable, Mapping

from qutebrowser.qt import machinery
from qutebrowser.qt.core import Qt, QEvent
from qutebrowser.qt.gui import QKeySequence, QKeyEvent
if machinery.IS_QT6:
    from qutebrowser.qt.core import QKeyCombination
else:
    QKeyCombination: None = None  # QKeyCombination was added in Qt 6

from qutebrowser.utils import utils, qtutils, debug


class InvalidKeyError(Exception):

    """Raised when a key can't be represented by PyQt.

    WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2022-April/044607.html
    Should be fixed in PyQt 6.3.1 (or 6.4.0?).
    """


# Map Qt::Key values to their Qt::KeyboardModifier value.
_MODIFIER_MAP = {
    Qt.Key.Key_Shift: Qt.KeyboardModifier.ShiftModifier,
    Qt.Key.Key_Control: Qt.KeyboardModifier.ControlModifier,
    Qt.Key.Key_Alt: Qt.KeyboardModifier.AltModifier,
    Qt.Key.Key_Meta: Qt.KeyboardModifier.MetaModifier,
    Qt.Key.Key_AltGr: Qt.KeyboardModifier.GroupSwitchModifier,
    Qt.Key.Key_Mode_switch: Qt.KeyboardModifier.GroupSwitchModifier,
}

try:
    _NIL_KEY: Union[Qt.Key, int] = Qt.Key(0)
except ValueError:
    # WORKAROUND for
    # https://www.riverbankcomputing.com/pipermail/pyqt/2022-April/044607.html
    _NIL_KEY = 0

if machinery.IS_QT6:
    _KeyInfoType = QKeyCombination
    _ModifierType = Qt.KeyboardModifier
else:
    _KeyInfoType = int
    _ModifierType = Union[Qt.KeyboardModifiers, Qt.KeyboardModifier]


_SPECIAL_NAMES = {
    # Some keys handled in a weird way by QKeySequence::toString.
    # See https://bugreports.qt.io/browse/QTBUG-40030
    # Most are unlikely to be ever needed, but you never know ;)
    # For dead/combining keys, we return the corresponding non-combining
    # key, as that's easier to add to the config.

    Qt.Key.Key_Super_L: 'Super L',
    Qt.Key.Key_Super_R: 'Super R',
    Qt.Key.Key_Hyper_L: 'Hyper L',
    Qt.Key.Key_Hyper_R: 'Hyper R',
    Qt.Key.Key_Direction_L: 'Direction L',
    Qt.Key.Key_Direction_R: 'Direction R',

    Qt.Key.Key_Shift: 'Shift',
    Qt.Key.Key_Control: 'Control',
    Qt.Key.Key_Meta: 'Meta',
    Qt.Key.Key_Alt: 'Alt',
    Qt.Key.Key_AltGr: 'AltGr',

    Qt.Key.Key_Multi_key: 'Multi key',
    Qt.Key.Key_SingleCandidate: 'Single Candidate',
    Qt.Key.Key_Mode_switch: 'Mode switch',

    Qt.Key.Key_Dead_Grave: '`',
    Qt.Key.Key_Dead_Acute: '´',
    Qt.Key.Key_Dead_Circumflex: '^',
    Qt.Key.Key_Dead_Tilde: '~',
    Qt.Key.Key_Dead_Macron: '¯',
    Qt.Key.Key_Dead_Breve: '˘',
    Qt.Key.Key_Dead_Abovedot: '˙',
    Qt.Key.Key_Dead_Diaeresis: '¨',
    Qt.Key.Key_Dead_Abovering: '˚',
    Qt.Key.Key_Dead_Doubleacute: '˝',
    Qt.Key.Key_Dead_Caron: 'ˇ',
    Qt.Key.Key_Dead_Cedilla: '¸',
    Qt.Key.Key_Dead_Ogonek: '˛',
    Qt.Key.Key_Dead_Iota: 'Iota',
    Qt.Key.Key_Dead_Voiced_Sound: 'Voiced Sound',
    Qt.Key.Key_Dead_Semivoiced_Sound: 'Semivoiced Sound',
    Qt.Key.Key_Dead_Belowdot: 'Belowdot',
    Qt.Key.Key_Dead_Hook: 'Hook',
    Qt.Key.Key_Dead_Horn: 'Horn',
    Qt.Key.Key_Dead_Stroke: '\u0335',  # '̵'
    Qt.Key.Key_Dead_Abovecomma: '\u0313',  # '̓'
    Qt.Key.Key_Dead_Abovereversedcomma: '\u0314',  # '̔'
    Qt.Key.Key_Dead_Doublegrave: '\u030f',  # '̏'
    Qt.Key.Key_Dead_Belowring: '\u0325',  # '̥'
    Qt.Key.Key_Dead_Belowmacron: '\u0331',  # '̱'
    Qt.Key.Key_Dead_Belowcircumflex: '\u032d',  # '̭'
    Qt.Key.Key_Dead_Belowtilde: '\u0330',  # '̰'
    Qt.Key.Key_Dead_Belowbreve: '\u032e',  # '̮'
    Qt.Key.Key_Dead_Belowdiaeresis: '\u0324',  # '̤'
    Qt.Key.Key_Dead_Invertedbreve: '\u0311',  # '̑'
    Qt.Key.Key_Dead_Belowcomma: '\u0326',  # '̦'
    Qt.Key.Key_Dead_Currency: '¤',
    Qt.Key.Key_Dead_a: 'a',
    Qt.Key.Key_Dead_A: 'A',
    Qt.Key.Key_Dead_e: 'e',
    Qt.Key.Key_Dead_E: 'E',
    Qt.Key.Key_Dead_i: 'i',
    Qt.Key.Key_Dead_I: 'I',
    Qt.Key.Key_Dead_o: 'o',
    Qt.Key.Key_Dead_O: 'O',
    Qt.Key.Key_Dead_u: 'u',
    Qt.Key.Key_Dead_U: 'U',
    Qt.Key.Key_Dead_Small_Schwa: 'ə',
    Qt.Key.Key_Dead_Capital_Schwa: 'Ə',
    Qt.Key.Key_Dead_Greek: 'Greek',
    Qt.Key.Key_Dead_Lowline: '\u0332',  # '̲'
    Qt.Key.Key_Dead_Aboveverticalline: '\u030d',  # '̍'
    Qt.Key.Key_Dead_Belowverticalline: '\u0329',
    Qt.Key.Key_Dead_Longsolidusoverlay: '\u0338',  # '̸'

    Qt.Key.Key_MediaLast: 'Media Last',

    Qt.Key.Key_unknown: 'Unknown',

    # For some keys, we just want a different name
    Qt.Key.Key_Escape: 'Escape',

    _NIL_KEY: 'nil',
}


def _assert_plain_key(key: Qt.Key) -> None:
    """Make sure this is a key without KeyboardModifier mixed in."""
    key_int = qtutils.extract_enum_val(key)
    mask = qtutils.extract_enum_val(Qt.KeyboardModifier.KeyboardModifierMask)
    assert not key_int & mask, hex(key_int)


def _assert_plain_modifier(key: _ModifierType) -> None:
    """Make sure this is a modifier without a key mixed in."""
    key_int = qtutils.extract_enum_val(key)
    mask = qtutils.extract_enum_val(Qt.KeyboardModifier.KeyboardModifierMask)
    assert not key_int & ~mask, hex(key_int)


def _is_printable(key: Qt.Key) -> bool:
    _assert_plain_key(key)
    return key <= 0xff and key not in [Qt.Key.Key_Space, _NIL_KEY]


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
        i = qtutils.extract_enum_val(data)
        raise ValueError(f"Invalid encoding in 0x{i:x} -> {s}: {e}")


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
    """Convert the given Qt::KeyboardModifier to a string.

    Handles Qt.KeyboardModifier.GroupSwitchModifier because Qt doesn't handle that as a
    modifier.
    """
    _assert_plain_modifier(modifiers)
    altgr = Qt.KeyboardModifier.GroupSwitchModifier
    if modifiers & altgr:
        modifiers = _unset_modifier_bits(modifiers, altgr)
        result = 'AltGr+'
    else:
        result = ''

    result += QKeySequence(qtutils.extract_enum_val(modifiers)).toString()

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


def _unset_modifier_bits(
    modifiers: _ModifierType, mask: _ModifierType
) -> _ModifierType:
    """Unset all bits in modifiers which are given in mask.

    Equivalent to modifiers & ~mask, but with a WORKAROUND with PyQt 6,
    for a bug in Python 3.11.4 where that isn't possible with an enum.Flag...:
    https://github.com/python/cpython/issues/105497
    """
    if machinery.IS_QT5:
        return Qt.KeyboardModifiers(modifiers & ~mask)  # can lose type if it's 0
    else:
        return Qt.KeyboardModifier(modifiers.value & ~mask.value)


@dataclasses.dataclass(frozen=True, order=True)
class KeyInfo:

    """A key with optional modifiers.

    Attributes:
        key: A Qt::Key member.
        modifiers: A Qt::KeyboardModifier enum value.
    """

    key: Qt.Key
    modifiers: _ModifierType = Qt.KeyboardModifier.NoModifier

    def __post_init__(self) -> None:
        """Run some validation on the key/modifier values."""
        # This changed with Qt 6, and e.g. to_qt() relies on this.
        if machinery.IS_QT5:
            modifier_classes = (Qt.KeyboardModifier, Qt.KeyboardModifiers)
        elif machinery.IS_QT6:
            modifier_classes = Qt.KeyboardModifier
        else:
            raise utils.Unreachable()
        assert isinstance(self.key, Qt.Key), self.key
        assert isinstance(self.modifiers, modifier_classes), self.modifiers

        _assert_plain_key(self.key)
        _assert_plain_modifier(self.modifiers)

    def __repr__(self) -> str:
        return utils.get_repr(
            self,
            key=debug.qenum_key(Qt, self.key, klass=Qt.Key),
            modifiers=debug.qflags_key(Qt, self.modifiers, klass=Qt.KeyboardModifier),
            text=str(self),
        )

    @classmethod
    def from_event(cls, e: QKeyEvent) -> 'KeyInfo':
        """Get a KeyInfo object from a QKeyEvent.

        This makes sure that key/modifiers are never mixed and also remaps
        UTF-16 surrogates to work around QTBUG-72776.
        """
        try:
            key = Qt.Key(e.key())
        except ValueError as ex:
            raise InvalidKeyError(str(ex))
        key = _remap_unicode(key, e.text())
        modifiers = e.modifiers()
        return cls(key, modifiers)

    @classmethod
    def from_qt(cls, combination: _KeyInfoType) -> 'KeyInfo':
        """Construct a KeyInfo from a Qt5-style int or Qt6-style QKeyCombination."""
        if machinery.IS_QT5:
            assert isinstance(combination, int)
            key = Qt.Key(
                int(combination) & ~Qt.KeyboardModifier.KeyboardModifierMask)
            modifiers = Qt.KeyboardModifier(
                int(combination) & Qt.KeyboardModifier.KeyboardModifierMask)
            return cls(key, modifiers)
        else:
            # QKeyCombination is now guaranteed to be available here
            assert isinstance(combination, QKeyCombination)
            try:
                key = combination.key()
            except ValueError as e:
                raise InvalidKeyError(str(e))
            return cls(
                key=key,
                modifiers=combination.keyboardModifiers(),
            )

    def __str__(self) -> str:
        """Convert this KeyInfo to a meaningful name.

        Return:
            A name of the key (combination) as a string.
        """
        key_string = _key_to_string(self.key)
        modifiers = self.modifiers

        if self.key in _MODIFIER_MAP:
            # Don't return e.g. <Shift+Shift>
            modifiers = _unset_modifier_bits(modifiers, _MODIFIER_MAP[self.key])
        elif _is_printable(self.key):
            # "normal" binding
            if not key_string:  # pragma: no cover
                raise ValueError("Got empty string for key 0x{:x}!"
                                 .format(self.key))

            assert len(key_string) == 1, key_string
            if self.modifiers == Qt.KeyboardModifier.ShiftModifier:
                assert not self.is_special()
                return key_string.upper()
            elif self.modifiers == Qt.KeyboardModifier.NoModifier:
                assert not self.is_special()
                return key_string.lower()
            else:
                # Use special binding syntax, but <Ctrl-a> instead of <Ctrl-A>
                key_string = key_string.lower()

        modifiers = Qt.KeyboardModifier(modifiers)

        # "special" binding
        assert self.is_special()
        modifier_string = _modifiers_to_string(modifiers)
        return '<{}{}>'.format(modifier_string, key_string)

    def text(self) -> str:
        """Get the text which would be displayed when pressing this key."""
        control = {
            Qt.Key.Key_Space: ' ',
            Qt.Key.Key_Tab: '\t',
            Qt.Key.Key_Backspace: '\b',
            Qt.Key.Key_Return: '\r',
            Qt.Key.Key_Enter: '\r',
            Qt.Key.Key_Escape: '\x1b',
        }

        if self.key in control:
            return control[self.key]
        elif not _is_printable(self.key):
            return ''

        text = QKeySequence(self.key).toString()
        if not self.modifiers & Qt.KeyboardModifier.ShiftModifier:
            text = text.lower()
        return text

    def to_event(self, typ: QEvent.Type = QEvent.Type.KeyPress) -> QKeyEvent:
        """Get a QKeyEvent from this KeyInfo."""
        return QKeyEvent(typ, self.key, self.modifiers, self.text())

    def to_qt(self) -> _KeyInfoType:
        """Get something suitable for a QKeySequence."""
        if machinery.IS_QT5:
            return int(self.key) | int(self.modifiers)
        else:
            return QKeyCombination(self.modifiers, self.key)

    def with_stripped_modifiers(self, modifiers: Qt.KeyboardModifier) -> "KeyInfo":
        mods = _unset_modifier_bits(self.modifiers, modifiers)
        return KeyInfo(key=self.key, modifiers=mods)

    def is_special(self) -> bool:
        """Check whether this key requires special key syntax."""
        return not (
            _is_printable(self.key) and
            self.modifiers in [
                Qt.KeyboardModifier.ShiftModifier,
                Qt.KeyboardModifier.NoModifier,
            ]
        )

    def is_modifier_key(self) -> bool:
        """Test whether the given key is a modifier.

        This only considers keys which are part of Qt::KeyboardModifier, i.e.
        which would interrupt a key chain like "yY" when handled.
        """
        return self.key in _MODIFIER_MAP


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

    def __init__(self, *keys: KeyInfo) -> None:
        self._sequences: list[QKeySequence] = []
        for sub in utils.chunk(keys, self._MAX_LEN):
            try:
                args = [info.to_qt() for info in sub]
            except InvalidKeyError as e:
                raise KeyParseError(keystr=None, error=f"Got invalid key: {e}")

            sequence = QKeySequence(*args)
            self._sequences.append(sequence)
        if keys:
            assert self
        self._validate()

    def __str__(self) -> str:
        parts = []
        for info in self:
            parts.append(str(info))
        return ''.join(parts)

    def __iter__(self) -> Iterator[KeyInfo]:
        """Iterate over KeyInfo objects."""
        # FIXME:mypy Stubs seem to be unaware that iterating a QKeySequence produces
        # _KeyInfoType
        sequences = cast(list[Iterable[_KeyInfoType]], self._sequences)
        for combination in itertools.chain.from_iterable(sequences):
            yield KeyInfo.from_qt(combination)

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
        infos = list(self)
        if isinstance(item, slice):
            return self.__class__(*infos[item])
        else:
            return infos[item]

    def _validate(self, keystr: str = None) -> None:
        try:
            for info in self:
                if info.key < Qt.Key.Key_Space or info.key >= Qt.Key.Key_unknown:
                    raise KeyParseError(keystr, "Got invalid key!")
        except InvalidKeyError as e:
            raise KeyParseError(keystr, f"Got invalid key: {e}")

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
            return QKeySequence.SequenceMatch.NoMatch

        for entered, configured in zip(self._sequences, other._sequences):
            # If we get NoMatch/PartialMatch in a sequence, we can abort there.
            match = entered.matches(configured)
            if match != QKeySequence.SequenceMatch.ExactMatch:
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
            return QKeySequence.SequenceMatch.ExactMatch
        elif len(self._sequences) < len(other._sequences):
            return QKeySequence.SequenceMatch.PartialMatch
        else:
            raise utils.Unreachable("self={!r} other={!r}".format(self, other))

    def append_event(self, ev: QKeyEvent) -> 'KeySequence':
        """Create a new KeySequence object with the given QKeyEvent added."""
        try:
            key = Qt.Key(ev.key())
        except ValueError as e:
            raise KeyParseError(None, f"Got invalid key: {e}")

        _assert_plain_key(key)
        _assert_plain_modifier(ev.modifiers())

        key = _remap_unicode(key, ev.text())
        modifiers: _ModifierType = ev.modifiers()

        if key == _NIL_KEY:
            raise KeyParseError(None, "Got nil key!")

        # We always remove Qt.KeyboardModifier.GroupSwitchModifier because QKeySequence has no
        # way to mention that in a binding anyways...
        modifiers = _unset_modifier_bits(modifiers, Qt.KeyboardModifier.GroupSwitchModifier)

        # We change Qt.Key.Key_Backtab to Key_Tab here because nobody would
        # configure "Shift-Backtab" in their config.
        if modifiers & Qt.KeyboardModifier.ShiftModifier and key == Qt.Key.Key_Backtab:
            key = Qt.Key.Key_Tab

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
        shift_modifier = Qt.KeyboardModifier.ShiftModifier
        if (modifiers == shift_modifier and
                _is_printable(key) and
                not ev.text().isupper()):
            modifiers = Qt.KeyboardModifier.NoModifier

        # On macOS, swap Ctrl and Meta back
        #
        # We don't use Qt.ApplicationAttribute.AA_MacDontSwapCtrlAndMeta because that also affects
        # Qt/QtWebEngine's own shortcuts. However, we do want "Ctrl" and "Meta"
        # (or "Cmd") in a key binding name to actually represent what's on the
        # keyboard.
        if utils.is_mac:
            if modifiers & Qt.KeyboardModifier.ControlModifier and modifiers & Qt.KeyboardModifier.MetaModifier:
                pass
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                modifiers = _unset_modifier_bits(modifiers, Qt.KeyboardModifier.ControlModifier)
                modifiers |= Qt.KeyboardModifier.MetaModifier
            elif modifiers & Qt.KeyboardModifier.MetaModifier:
                modifiers = _unset_modifier_bits(modifiers, Qt.KeyboardModifier.MetaModifier)
                modifiers |= Qt.KeyboardModifier.ControlModifier

        infos = list(self)
        infos.append(KeyInfo(key, modifiers))

        return self.__class__(*infos)

    def strip_modifiers(self) -> 'KeySequence':
        """Strip optional modifiers from keys."""
        modifiers = Qt.KeyboardModifier.KeypadModifier
        infos = [info.with_stripped_modifiers(modifiers) for info in self]
        return self.__class__(*infos)

    def with_mappings(
            self,
            mappings: Mapping['KeySequence', 'KeySequence']
    ) -> 'KeySequence':
        """Get a new KeySequence with the given mappings applied."""
        infos: list[KeyInfo] = []
        for info in self:
            key_seq = KeySequence(info)
            if key_seq in mappings:
                infos += mappings[key_seq]
            else:
                infos.append(info)
        return self.__class__(*infos)

    @classmethod
    def parse(cls, keystr: str) -> 'KeySequence':
        """Parse a keystring like <Ctrl-x> or xyz and return a KeySequence."""
        new = cls()
        strings = list(_parse_keystring(keystr))
        for sub in utils.chunk(strings, cls._MAX_LEN):
            sequence = QKeySequence(', '.join(sub))
            new._sequences.append(sequence)

        if keystr:
            assert new, keystr

        new._validate(keystr)
        return new
