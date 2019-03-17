# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Our own QKeySequence-like class and related utilities."""

import itertools

import attr
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeySequence, QKeyEvent

from qutebrowser.utils import utils


# Map Qt::Key values to their Qt::KeyboardModifier value.
_MODIFIER_MAP = {
    Qt.Key_Shift: Qt.ShiftModifier,
    Qt.Key_Control: Qt.ControlModifier,
    Qt.Key_Alt: Qt.AltModifier,
    Qt.Key_Meta: Qt.MetaModifier,
    Qt.Key_Mode_switch: Qt.GroupSwitchModifier,
}


def _assert_plain_key(key):
    """Make sure this is a key without KeyboardModifiers mixed in."""
    assert not key & Qt.KeyboardModifierMask, hex(key)


def _assert_plain_modifier(key):
    """Make sure this is a modifier without a key mixed in."""
    assert not key & ~Qt.KeyboardModifierMask, hex(key)


def _is_printable(key):
    _assert_plain_key(key)
    return key <= 0xff and key not in [Qt.Key_Space, 0x0]


def is_special(key, modifiers):
    """Check whether this key requires special key syntax."""
    _assert_plain_key(key)
    _assert_plain_modifier(modifiers)
    return not (_is_printable(key) and
                modifiers in [Qt.ShiftModifier, Qt.NoModifier,
                              Qt.KeypadModifier])


def is_modifier_key(key):
    """Test whether the given key is a modifier.

    This only considers keys which are part of Qt::KeyboardModifiers, i.e.
    which would interrupt a key chain like "yY" when handled.
    """
    _assert_plain_key(key)
    return key in _MODIFIER_MAP


def _check_valid_utf8(s, data):
    """Make sure the given string is valid UTF-8.

    Makes sure there are no chars where Qt did fall back to weird UTF-16
    surrogates.
    """
    try:
        s.encode('utf-8')
    except UnicodeEncodeError as e:  # pragma: no cover
        raise ValueError("Invalid encoding in 0x{:x} -> {}: {}"
                         .format(data, s, e))


def _key_to_string(key):
    """Convert a Qt::Key member to a meaningful name.

    Args:
        key: A Qt::Key member.

    Return:
        A name of the key as a string.
    """
    _assert_plain_key(key)
    special_names_str = {
        # Some keys handled in a weird way by QKeySequence::toString.
        # See https://bugreports.qt.io/browse/QTBUG-40030
        # Most are unlikely to be ever needed, but you never know ;)
        # For dead/combining keys, we return the corresponding non-combining
        # key, as that's easier to add to the config.

        'Super_L': 'Super L',
        'Super_R': 'Super R',
        'Hyper_L': 'Hyper L',
        'Hyper_R': 'Hyper R',
        'Direction_L': 'Direction L',
        'Direction_R': 'Direction R',

        'Shift': 'Shift',
        'Control': 'Control',
        'Meta': 'Meta',
        'Alt': 'Alt',

        'AltGr': 'AltGr',
        'Multi_key': 'Multi key',
        'SingleCandidate': 'Single Candidate',
        'Mode_switch': 'Mode switch',
        'Dead_Grave': '`',
        'Dead_Acute': '´',
        'Dead_Circumflex': '^',
        'Dead_Tilde': '~',
        'Dead_Macron': '¯',
        'Dead_Breve': '˘',
        'Dead_Abovedot': '˙',
        'Dead_Diaeresis': '¨',
        'Dead_Abovering': '˚',
        'Dead_Doubleacute': '˝',
        'Dead_Caron': 'ˇ',
        'Dead_Cedilla': '¸',
        'Dead_Ogonek': '˛',
        'Dead_Iota': 'Iota',
        'Dead_Voiced_Sound': 'Voiced Sound',
        'Dead_Semivoiced_Sound': 'Semivoiced Sound',
        'Dead_Belowdot': 'Belowdot',
        'Dead_Hook': 'Hook',
        'Dead_Horn': 'Horn',

        'Dead_Stroke': '̵',
        'Dead_Abovecomma': '̓',
        'Dead_Abovereversedcomma': '̔',
        'Dead_Doublegrave': '̏',
        'Dead_Belowring': '̥',
        'Dead_Belowmacron': '̱',
        'Dead_Belowcircumflex': '̭',
        'Dead_Belowtilde': '̰',
        'Dead_Belowbreve': '̮',
        'Dead_Belowdiaeresis': '̤',
        'Dead_Invertedbreve': '̑',
        'Dead_Belowcomma': '̦',
        'Dead_Currency': '¤',
        'Dead_a': 'a',
        'Dead_A': 'A',
        'Dead_e': 'e',
        'Dead_E': 'E',
        'Dead_i': 'i',
        'Dead_I': 'I',
        'Dead_o': 'o',
        'Dead_O': 'O',
        'Dead_u': 'u',
        'Dead_U': 'U',
        'Dead_Small_Schwa': 'ə',
        'Dead_Capital_Schwa': 'Ə',
        'Dead_Greek': 'Greek',
        'Dead_Lowline': '̲',
        'Dead_Aboveverticalline': '̍',
        'Dead_Belowverticalline': '\u0329',
        'Dead_Longsolidusoverlay': '̸',

        'Memo': 'Memo',
        'ToDoList': 'To Do List',
        'Calendar': 'Calendar',
        'ContrastAdjust': 'Contrast Adjust',
        'LaunchG': 'Launch (G)',
        'LaunchH': 'Launch (H)',

        'MediaLast': 'Media Last',

        'unknown': 'Unknown',

        # For some keys, we just want a different name
        'Escape': 'Escape',
    }
    # We now build our real special_names dict from the string mapping above.
    # The reason we don't do this directly is that certain Qt versions don't
    # have all the keys, so we want to ignore AttributeErrors.
    special_names = {}
    for k, v in special_names_str.items():
        try:
            special_names[getattr(Qt, 'Key_' + k)] = v
        except AttributeError:
            pass
        special_names[0x0] = 'nil'

    if key in special_names:
        return special_names[key]

    result = QKeySequence(key).toString()
    _check_valid_utf8(result, key)
    return result


def _modifiers_to_string(modifiers):
    """Convert the given Qt::KeyboardModifiers to a string.

    Handles Qt.GroupSwitchModifier because Qt doesn't handle that as a
    modifier.
    """
    _assert_plain_modifier(modifiers)
    if modifiers & Qt.GroupSwitchModifier:
        modifiers &= ~Qt.GroupSwitchModifier
        result = 'AltGr+'
    else:
        result = ''

    result += QKeySequence(modifiers).toString()

    _check_valid_utf8(result, modifiers)
    return result


class KeyParseError(Exception):

    """Raised by _parse_single_key/parse_keystring on parse errors."""

    def __init__(self, keystr, error):
        if keystr is None:
            msg = "Could not parse keystring: {}".format(error)
        else:
            msg = "Could not parse {!r}: {}".format(keystr, error)
        super().__init__(msg)


def _parse_keystring(keystr):
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


def _parse_special_key(keystr):
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
        ('mod1', 'alt'),
        ('less', '<'),
        ('greater', '>'),
    )
    for (orig, repl) in replacements:
        keystr = keystr.replace(orig, repl)

    for mod in ['ctrl', 'meta', 'alt', 'shift', 'num']:
        keystr = keystr.replace(mod + '-', mod + '+')
    return keystr


def _parse_single_key(keystr):
    """Get a keystring for QKeySequence for a single key."""
    return 'Shift+' + keystr if keystr.isupper() else keystr


@attr.s
class KeyInfo:

    """A key with optional modifiers.

    Attributes:
        key: A Qt::Key member.
        modifiers: A Qt::KeyboardModifiers enum value.
    """

    key = attr.ib()
    modifiers = attr.ib()

    @classmethod
    def from_event(cls, e):
        return cls(e.key(), e.modifiers())

    def __str__(self):
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

        # "special" binding
        assert (is_special(self.key, self.modifiers) or
                self.modifiers == Qt.KeypadModifier)
        modifier_string = _modifiers_to_string(modifiers)
        return '<{}{}>'.format(modifier_string, key_string)

    def text(self):
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
        if not self.modifiers & Qt.ShiftModifier:
            text = text.lower()
        return text

    def to_event(self, typ=QEvent.KeyPress):
        """Get a QKeyEvent from this KeyInfo."""
        return QKeyEvent(typ, self.key, self.modifiers, self.text())

    def to_int(self):
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

    def __init__(self, *keys):
        self._sequences = []
        for sub in utils.chunk(keys, self._MAX_LEN):
            sequence = QKeySequence(*sub)
            self._sequences.append(sequence)
        if keys:
            assert self
        self._validate()

    def __str__(self):
        parts = []
        for info in self:
            parts.append(str(info))
        return ''.join(parts)

    def __iter__(self):
        """Iterate over KeyInfo objects."""
        for key_and_modifiers in self._iter_keys():
            key = int(key_and_modifiers) & ~Qt.KeyboardModifierMask
            modifiers = Qt.KeyboardModifiers(int(key_and_modifiers) &
                                             Qt.KeyboardModifierMask)
            yield KeyInfo(key=key, modifiers=modifiers)

    def __repr__(self):
        return utils.get_repr(self, keys=str(self))

    def __lt__(self, other):
        # pylint: disable=protected-access
        return self._sequences < other._sequences

    def __gt__(self, other):
        # pylint: disable=protected-access
        return self._sequences > other._sequences

    def __le__(self, other):
        # pylint: disable=protected-access
        return self._sequences <= other._sequences

    def __ge__(self, other):
        # pylint: disable=protected-access
        return self._sequences >= other._sequences

    def __eq__(self, other):
        # pylint: disable=protected-access
        return self._sequences == other._sequences

    def __ne__(self, other):
        # pylint: disable=protected-access
        return self._sequences != other._sequences

    def __hash__(self):
        return hash(tuple(self._sequences))

    def __len__(self):
        return sum(len(seq) for seq in self._sequences)

    def __bool__(self):
        return bool(self._sequences)

    def __getitem__(self, item):
        if isinstance(item, slice):
            keys = list(self._iter_keys())
            return self.__class__(*keys[item])
        else:
            infos = list(self)
            return infos[item]

    def _iter_keys(self):
        return itertools.chain.from_iterable(self._sequences)

    def _validate(self, keystr=None):
        for info in self:
            if info.key < Qt.Key_Space or info.key >= Qt.Key_unknown:
                raise KeyParseError(keystr, "Got invalid key!")

        for seq in self._sequences:
            if not seq:
                raise KeyParseError(keystr, "Got invalid key!")

    def matches(self, other):
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

    def append_event(self, ev):
        """Create a new KeySequence object with the given QKeyEvent added."""
        key = ev.key()
        modifiers = ev.modifiers()

        _assert_plain_key(key)
        _assert_plain_modifier(modifiers)

        if key == 0x0:
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
                _is_printable(ev.key()) and
                not ev.text().isupper()):
            modifiers = Qt.KeyboardModifiers()

        # On macOS, swap Ctrl and Meta back
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-51293
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

    def strip_modifiers(self):
        """Strip optional modifiers from keys."""
        modifiers = Qt.KeypadModifier
        keys = [key & ~modifiers for key in self._iter_keys()]
        return self.__class__(*keys)

    def with_mappings(self, mappings):
        """Get a new KeySequence with the given mappings applied."""
        keys = []
        for key in self._iter_keys():
            key_seq = KeySequence(key)
            if key_seq in mappings:
                new_seq = mappings[key_seq]
                assert len(new_seq) == 1
                key = new_seq[0].to_int()
            keys.append(key)
        return self.__class__(*keys)

    @classmethod
    def parse(cls, keystr):
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
