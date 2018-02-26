# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import unicodedata
import collections
import itertools

import attr
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

from qutebrowser.utils import utils, debug


def key_to_string(key):
    """Convert a Qt::Key member to a meaningful name.

    Args:
        key: A Qt::Key member.

    Return:
        A name of the key as a string.
    """
    special_names_str = {
        # Some keys handled in a weird way by QKeySequence::toString.
        # See https://bugreports.qt.io/browse/QTBUG-40030
        # Most are unlikely to be ever needed, but you never know ;)
        # For dead/combining keys, we return the corresponding non-combining
        # key, as that's easier to add to the config.
        'Key_Blue': 'Blue',
        'Key_Calendar': 'Calendar',
        'Key_ChannelDown': 'Channel Down',
        'Key_ChannelUp': 'Channel Up',
        'Key_ContrastAdjust': 'Contrast Adjust',
        'Key_Dead_Abovedot': '˙',
        'Key_Dead_Abovering': '˚',
        'Key_Dead_Acute': '´',
        'Key_Dead_Belowdot': 'Belowdot',
        'Key_Dead_Breve': '˘',
        'Key_Dead_Caron': 'ˇ',
        'Key_Dead_Cedilla': '¸',
        'Key_Dead_Circumflex': '^',
        'Key_Dead_Diaeresis': '¨',
        'Key_Dead_Doubleacute': '˝',
        'Key_Dead_Grave': '`',
        'Key_Dead_Hook': 'Hook',
        'Key_Dead_Horn': 'Horn',
        'Key_Dead_Iota': 'Iota',
        'Key_Dead_Macron': '¯',
        'Key_Dead_Ogonek': '˛',
        'Key_Dead_Semivoiced_Sound': 'Semivoiced Sound',
        'Key_Dead_Tilde': '~',
        'Key_Dead_Voiced_Sound': 'Voiced Sound',
        'Key_Exit': 'Exit',
        'Key_Green': 'Green',
        'Key_Guide': 'Guide',
        'Key_Info': 'Info',
        'Key_LaunchG': 'LaunchG',
        'Key_LaunchH': 'LaunchH',
        'Key_MediaLast': 'MediaLast',
        'Key_Memo': 'Memo',
        'Key_MicMute': 'Mic Mute',
        'Key_Mode_switch': 'Mode switch',
        'Key_Multi_key': 'Multi key',
        'Key_PowerDown': 'Power Down',
        'Key_Red': 'Red',
        'Key_Settings': 'Settings',
        'Key_SingleCandidate': 'Single Candidate',
        'Key_ToDoList': 'Todo List',
        'Key_TouchpadOff': 'Touchpad Off',
        'Key_TouchpadOn': 'Touchpad On',
        'Key_TouchpadToggle': 'Touchpad toggle',
        'Key_Yellow': 'Yellow',
        'Key_Alt': 'Alt',
        'Key_AltGr': 'AltGr',
        'Key_Control': 'Control',
        'Key_Direction_L': 'Direction L',
        'Key_Direction_R': 'Direction R',
        'Key_Hyper_L': 'Hyper L',
        'Key_Hyper_R': 'Hyper R',
        'Key_Meta': 'Meta',
        'Key_Shift': 'Shift',
        'Key_Super_L': 'Super L',
        'Key_Super_R': 'Super R',
        'Key_unknown': 'Unknown',
    }
    # We now build our real special_names dict from the string mapping above.
    # The reason we don't do this directly is that certain Qt versions don't
    # have all the keys, so we want to ignore AttributeErrors.
    special_names = {}
    for k, v in special_names_str.items():
        try:
            special_names[getattr(Qt, k)] = v
        except AttributeError:
            pass
    # Now we check if the key is any special one - if not, we use
    # QKeySequence::toString.
    try:
        return special_names[key]
    except KeyError:
        name = QKeySequence(key).toString()
        morphings = {
            'Backtab': 'Tab',
            'Esc': 'Escape',
        }
        if name in morphings:
            return morphings[name]
        else:
            return name


def keyevent_to_string(e):
    """Convert a QKeyEvent to a meaningful name."""
    return str(KeyInfo(e.key(), e.modifiers()))


class KeyParseError(Exception):

    """Raised by _parse_single_key/parse_keystring on parse errors."""

    def __init__(self, keystr, error):
        super().__init__("Could not parse {!r}: {}".format(keystr, error))


def _parse_keystring(keystr):
    key = ''
    special = False
    for c in keystr:
        if c == '>':
            yield normalize_keystr(key)
            key = ''
            special = False
        elif c == '<':
            special = True
        elif special:
            key += c
        else:
            yield 'Shift+' + c if c.isupper() else c


def normalize_keystr(keystr):
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
        ('mod1', 'alt'),
        ('mod4', 'meta'),
    )
    for (orig, repl) in replacements:
        keystr = keystr.replace(orig, repl)
    for mod in ['ctrl', 'meta', 'alt', 'shift']:
        keystr = keystr.replace(mod + '-', mod + '+')
    return keystr


@attr.s
class KeyInfo:

    """A key with optional modifiers.

    Attributes:
        key: A Qt::Key member.
        modifiers: A Qt::KeyboardModifiers enum value.
    """

    key = attr.ib()
    modifiers = attr.ib()

    def __str__(self):
        """Convert this KeyInfo to a meaningful name.

        Return:
            A name of the key (combination) as a string or
            an empty string if only modifiers are pressed.
        """
        if utils.is_mac:
            # Qt swaps Ctrl/Meta on macOS, so we switch it back here so the user
            # can use it in the config as expected. See:
            # https://github.com/qutebrowser/qutebrowser/issues/110
            # http://doc.qt.io/qt-5.4/osx-issues.html#special-keys
            modmask2str = collections.OrderedDict([
                (Qt.MetaModifier, 'Ctrl'),
                (Qt.AltModifier, 'Alt'),
                (Qt.ControlModifier, 'Meta'),
                (Qt.ShiftModifier, 'Shift'),
            ])
        else:
            modmask2str = collections.OrderedDict([
                (Qt.ControlModifier, 'Ctrl'),
                (Qt.AltModifier, 'Alt'),
                (Qt.MetaModifier, 'Meta'),
                (Qt.ShiftModifier, 'Shift'),
            ])

        modifier_keys = (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta,
                        Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R,
                        Qt.Key_Hyper_L, Qt.Key_Hyper_R, Qt.Key_Direction_L,
                        Qt.Key_Direction_R)
        if self.key in modifier_keys:
            # Only modifier pressed
            return ''
        parts = []

        for (mask, s) in modmask2str.items():
            if self.modifiers & mask and s not in parts:
                parts.append(s)

        key_string = key_to_string(self.key)

        if len(key_string) == 1:
            category = unicodedata.category(key_string)
            is_special_char = (category == 'Cc')
        else:
            is_special_char = False

        if not is_special_char:
            if self.modifiers == Qt.ShiftModifier:
                parts = []
                key_string = key_string.upper()
            else:
                key_string = key_string.lower()

        parts.append(key_string)
        part_string = '+'.join(parts)

        if len(part_string) > 1:
            # "special" binding
            return '<{}>'.format(part_string)
        else:
            # "normal" binding
            return part_string

    def text(self):
        """Get the text which would be displayed when pressing this key."""
        text = QKeySequence(self.key).toString()
        if not self.modifiers & Qt.ShiftModifier:
            text = text.lower()
        return text


class KeySequence:

    _MAX_LEN = 4

    def __init__(self, *keys):
        self._sequences = []
        for sub in utils.chunk(keys, self._MAX_LEN):
            sequence = QKeySequence(*sub)
            self._sequences.append(sequence)
        if keys:
            assert len(self) > 0
        self._validate()

    def __str__(self):
        parts = []
        for info in self:
            parts.append(str(info))
        return ''.join(parts)

    def __iter__(self):
        """Iterate over KeyInfo objects."""
        modifier_mask = int(Qt.ShiftModifier | Qt.ControlModifier |
                            Qt.AltModifier | Qt.MetaModifier |
                            Qt.KeypadModifier | Qt.GroupSwitchModifier)
        for key in self._iter_keys():
            yield KeyInfo(
                key=int(key) & ~modifier_mask,
                modifiers=Qt.KeyboardModifiers(int(key) & modifier_mask))

    def __repr__(self):
        return utils.get_repr(self, keys=str(self))

    def __lt__(self, other):
        return self._sequences < other._sequences

    def __gt__(self, other):
        return self._sequences > other._sequences

    def __eq__(self, other):
        return self._sequences == other._sequences

    def __ne__(self, other):
        return self._sequences != other._sequences

    def __hash__(self):
        # FIXME is this correct?
        return hash(tuple(self._sequences))

    def __len__(self):
        return sum(len(seq) for seq in self._sequences)

    def __getitem__(self, item):
        keys = list(self._iter_keys())
        return self.__class__(*keys[item])

    def _iter_keys(self):
        return itertools.chain.from_iterable(self._sequences)

    def _validate(self):
        for info in self:
            assert info.key != Qt.Key_unknown

    def matches(self, other):
        # FIXME test this
        # pylint: disable=protected-access
        assert self._sequences
        assert other._sequences
        for seq1, seq2 in zip(self._sequences, other._sequences):
            match = seq1.matches(seq2)
            if match != QKeySequence.ExactMatch:
                return match
        return QKeySequence.ExactMatch

    def append_event(self, ev):
        """Create a new KeySequence object with the given QKeyEvent added.

        We need to do some sophisticated checking of modifiers here:

        We don't care about a shift modifier with symbols (Shift-: should match
        a : binding even though we typed it with a shift on an US-keyboard)

        However, we *do* care about Shift being involved if we got an upper-case
        letter, as Shift-A should match a Shift-A binding, but not an "a"
        binding.

        In addition, Shift also *is* relevant when other modifiers are involved.
        Shift-Ctrl-X should not be equivalent to Ctrl-X.

        FIXME: create test cases!
        """
        # pylint: disable=protected-access
        modifiers = ev.modifiers()
        if (modifiers == Qt.ShiftModifier and
                ev.text() and
                unicodedata.category(ev.text()) != 'Lu'):
            modifiers = Qt.KeyboardModifiers()

        keys = list(self._iter_keys())
        keys.append(ev.key() | int(modifiers))

        return self.__class__(*keys)

    @classmethod
    def parse(cls, keystr):
        """Parse a keystring like <Ctrl-x> or xyz and return a KeySequence."""
        new = cls()
        strings = list(_parse_keystring(keystr))
        for sub in utils.chunk(strings, cls._MAX_LEN):
            sequence = QKeySequence(', '.join(sub))
            new._sequences.append(sequence)
        assert len(new) > 0
        new._validate()
        return new
