# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import attr

from PyQt5.QtCore import Qt


@attr.s
class Key:

    attribute = attr.ib()
    name = attr.ib(None)  # default: name == attribute
    text = attr.ib('')
    member = attr.ib(None)


# From enum Key in qt5/qtbase/src/corelib/global/qnamespace.h
KEYS = [
    ### misc keys
    Key('Escape'),
    Key('Tab'),
    Key('Backtab'),
    Key('Backspace'),
    Key('Return'),
    Key('Enter'),
    Key('Insert'),
    Key('Delete'),
    Key('Pause'),
    Key('Print'),  # print screen
    Key('SysReq'),
    Key('Clear'),
    ### cursor movement
    Key('Home'),
    Key('End'),
    Key('Left'),
    Key('Up'),
    Key('Right'),
    Key('Down'),
    Key('PageUp'),
    Key('PageDown'),
    ### modifiers
    Key('Shift'),
    Key('Control'),
    Key('Meta'),
    Key('Alt'),
    Key('CapsLock'),
    Key('NumLock'),
    Key('ScrollLock'),
    ### function keys
    Key('F1'),
    Key('F2'),
    Key('F3'),
    Key('F4'),
    Key('F5'),
    Key('F6'),
    Key('F7'),
    Key('F8'),
    Key('F9'),
    Key('F10'),
    Key('F11'),
    Key('F12'),
    Key('F13'),
    Key('F14'),
    Key('F15'),
    Key('F16'),
    Key('F17'),
    Key('F18'),
    Key('F19'),
    Key('F20'),
    Key('F21'),
    Key('F22'),
    Key('F23'),
    Key('F24'),
    # F25 .. F35 only on X11
    Key('F25'),
    Key('F26'),
    Key('F27'),
    Key('F28'),
    Key('F29'),
    Key('F30'),
    Key('F31'),
    Key('F32'),
    Key('F33'),
    Key('F34'),
    Key('F35'),
    ### extra keys
    Key('Super_L'),
    Key('Super_R'),
    Key('Menu'),
    Key('Hyper_L'),
    Key('Hyper_R'),
    Key('Help'),
    Key('Direction_L'),
    Key('Direction_R'),
    ### 7 bit printable ASCII
    Key('Space'),
    Key('Any'),
    Key('Exclam'),
    Key('QuoteDbl'),
    Key('NumberSign'),
    Key('Dollar'),
    Key('Percent'),
    Key('Ampersand'),
    Key('Apostrophe'),
    Key('ParenLeft'),
    Key('ParenRight'),
    Key('Asterisk'),
    Key('Plus'),
    Key('Comma'),
    Key('Minus'),
    Key('Period'),
    Key('Slash'),
    Key('0'),
    Key('1'),
    Key('2'),
    Key('3'),
    Key('4'),
    Key('5'),
    Key('6'),
    Key('7'),
    Key('8'),
    Key('9'),
    Key('Colon'),
    Key('Semicolon'),
    Key('Less'),
    Key('Equal'),
    Key('Greater'),
    Key('Question'),
    Key('At'),
    Key('A'),
    Key('B'),
    Key('C'),
    Key('D'),
    Key('E'),
    Key('F'),
    Key('G'),
    Key('H'),
    Key('I'),
    Key('J'),
    Key('K'),
    Key('L'),
    Key('M'),
    Key('N'),
    Key('O'),
    Key('P'),
    Key('Q'),
    Key('R'),
    Key('S'),
    Key('T'),
    Key('U'),
    Key('V'),
    Key('W'),
    Key('X'),
    Key('Y'),
    Key('Z'),
    Key('BracketLeft'),
    Key('Backslash'),
    Key('BracketRight'),
    Key('AsciiCircum'),
    Key('Underscore'),
    Key('QuoteLeft'),
    Key('BraceLeft'),
    Key('Bar'),
    Key('BraceRight'),
    Key('AsciiTilde'),

    Key('nobreakspace'),
    Key('exclamdown'),
    Key('cent'),
    Key('sterling'),
    Key('currency'),
    Key('yen'),
    Key('brokenbar'),
    Key('section'),
    Key('diaeresis'),
    Key('copyright'),
    Key('ordfeminine'),
    Key('guillemotleft'),    # left angle quotation mark
    Key('notsign'),
    Key('hyphen'),
    Key('registered'),
    Key('macron'),
    Key('degree'),
    Key('plusminus'),
    Key('twosuperior'),
    Key('threesuperior'),
    Key('acute'),
    Key('mu'),
    Key('paragraph'),
    Key('periodcentered'),
    Key('cedilla'),
    Key('onesuperior'),
    Key('masculine'),
    Key('guillemotright'),    # right angle quotation mark
    Key('onequarter'),
    Key('onehalf'),
    Key('threequarters'),
    Key('questiondown'),
    Key('Agrave'),
    Key('Aacute'),
    Key('Acircumflex'),
    Key('Atilde'),
    Key('Adiaeresis'),
    Key('Aring'),
    Key('AE'),
    Key('Ccedilla'),
    Key('Egrave'),
    Key('Eacute'),
    Key('Ecircumflex'),
    Key('Ediaeresis'),
    Key('Igrave'),
    Key('Iacute'),
    Key('Icircumflex'),
    Key('Idiaeresis'),
    Key('ETH'),
    Key('Ntilde'),
    Key('Ograve'),
    Key('Oacute'),
    Key('Ocircumflex'),
    Key('Otilde'),
    Key('Odiaeresis'),
    Key('multiply'),
    Key('Ooblique'),
    Key('Ugrave'),
    Key('Uacute'),
    Key('Ucircumflex'),
    Key('Udiaeresis'),
    Key('Yacute'),
    Key('THORN'),
    Key('ssharp'),
    Key('division'),
    Key('ydiaeresis'),

    ### International input method support (X keycode - 0xEE00, the
    ### definition follows Qt/Embedded 2.3.7) Only interesting if
    ### you are writing your own input method

    ### International & multi-key character composition
    Key('AltGr'),
    Key('Multi_key'),  # Multi-key character compose
    Key('Codeinput'),
    Key('SingleCandidate'),
    Key('MultipleCandidate'),
    Key('PreviousCandidate'),

    ### Misc Functions
    Key('Mode_switch'),  # Character set switch
    # Key('script_switch'),  # Alias for mode_switch

    ### Japanese keyboard support
    Key('Kanji'),  # Kanji, Kanji convert
    Key('Muhenkan'),  # Cancel Conversion
    # Key('Henkan_Mode'),  # Start/Stop Conversion
    Key('Henkan'),  # Alias for Henkan_Mode
    Key('Romaji'),  # to Romaji
    Key('Hiragana'),  # to Hiragana
    Key('Katakana'),  # to Katakana
    # Hiragana/Katakana toggle
    Key('Hiragana_Katakana'),
    Key('Zenkaku'),  # to Zenkaku
    Key('Hankaku'),  # to Hankaku
    Key('Zenkaku_Hankaku'),  # Zenkaku/Hankaku toggle
    Key('Touroku'),  # Add to Dictionary
    Key('Massyo'),  # Delete from Dictionary
    Key('Kana_Lock'),  # Kana Lock
    Key('Kana_Shift'),  # Kana Shift
    Key('Eisu_Shift'),  # Alphanumeric Shift
    Key('Eisu_toggle'),  # Alphanumeric toggle
    # Key('Kanji_Bangou'),  # Codeinput
    # Key('Zen_Koho'),  # Multiple/All Candidate(s)
    # Key('Mae_Koho'),  # Previous Candidate

    ### Korean keyboard support
    ###
    ### In fact, many Korean users need only 2 keys, Key_Hangul and
    ### Key_Hangul_Hanja. But rest of the keys are good for future.

    Key('Hangul'),  # Hangul start/stop(toggle)
    Key('Hangul_Start'),  # Hangul start
    Key('Hangul_End'),  # Hangul end, English start
    Key('Hangul_Hanja'),  # Start Hangul->Hanja Conversion
    Key('Hangul_Jamo'),  # Hangul Jamo mode
    Key('Hangul_Romaja'),  # Hangul Romaja mode
    # Key('Hangul_Codeinput'),# Hangul code input mode
    Key('Hangul_Jeonja'),  # Jeonja mode
    Key('Hangul_Banja'),  # Banja mode
    Key('Hangul_PreHanja'),  # Pre Hanja conversion
    Key('Hangul_PostHanja'),  # Post Hanja conversion
    # Key('Hangul_SingleCandidate'),  # Single candidate
    # Key('Hangul_MultipleCandidate'),  # Multiple candidate
    # Key('Hangul_PreviousCandidate'),  # Previous candidate
    Key('Hangul_Special'),  # Special symbols
    # Key('Hangul_switch'),  # Alias for mode_switch

    # dead keys (X keycode - 0xED00 to avoid the conflict)
    Key('Dead_Grave'),
    Key('Dead_Acute'),
    Key('Dead_Circumflex'),
    Key('Dead_Tilde'),
    Key('Dead_Macron'),
    Key('Dead_Breve'),
    Key('Dead_Abovedot'),
    Key('Dead_Diaeresis'),
    Key('Dead_Abovering'),
    Key('Dead_Doubleacute'),
    Key('Dead_Caron'),
    Key('Dead_Cedilla'),
    Key('Dead_Ogonek'),
    Key('Dead_Iota'),
    Key('Dead_Voiced_Sound'),
    Key('Dead_Semivoiced_Sound'),
    Key('Dead_Belowdot'),
    Key('Dead_Hook'),
    Key('Dead_Horn'),

    # Not in Qt 5.10, so data may be wrong!
    Key('Dead_Stroke'),
    Key('Dead_Abovecomma'),
    Key('Dead_Abovereversedcomma'),
    Key('Dead_Doublegrave'),
    Key('Dead_Belowring'),
    Key('Dead_Belowmacron'),
    Key('Dead_Belowcircumflex'),
    Key('Dead_Belowtilde'),
    Key('Dead_Belowbreve'),
    Key('Dead_Belowdiaeresis'),
    Key('Dead_Invertedbreve'),
    Key('Dead_Belowcomma'),
    Key('Dead_Currency'),
    Key('Dead_a'),
    Key('Dead_A'),
    Key('Dead_e'),
    Key('Dead_E'),
    Key('Dead_i'),
    Key('Dead_I'),
    Key('Dead_o'),
    Key('Dead_O'),
    Key('Dead_u'),
    Key('Dead_U'),
    Key('Dead_Small_Schwa'),
    Key('Dead_Capital_Schwa'),
    Key('Dead_Greek'),
    Key('Dead_Lowline'),
    Key('Dead_Aboveverticalline'),
    Key('Dead_Belowverticalline'),
    Key('Dead_Longsolidusoverlay'),

    ### multimedia/internet keys - ignored by default - see QKeyEvent c'tor
    Key('Back'),
    Key('Forward'),
    Key('Stop'),
    Key('Refresh'),
    Key('VolumeDown'),
    Key('VolumeMute'),
    Key('VolumeUp'),
    Key('BassBoost'),
    Key('BassUp'),
    Key('BassDown'),
    Key('TrebleUp'),
    Key('TrebleDown'),
    Key('MediaPlay'),
    Key('MediaStop'),
    Key('MediaPrevious'),
    Key('MediaNext'),
    Key('MediaRecord'),
    Key('MediaPause'),
    Key('MediaTogglePlayPause'),
    Key('HomePage'),
    Key('Favorites'),
    Key('Search'),
    Key('Standby'),
    Key('OpenUrl'),
    Key('LaunchMail'),
    Key('LaunchMedia'),
    Key('Launch0'),
    Key('Launch1'),
    Key('Launch2'),
    Key('Launch3'),
    Key('Launch4'),
    Key('Launch5'),
    Key('Launch6'),
    Key('Launch7'),
    Key('Launch8'),
    Key('Launch9'),
    Key('LaunchA'),
    Key('LaunchB'),
    Key('LaunchC'),
    Key('LaunchD'),
    Key('LaunchE'),
    Key('LaunchF'),
    Key('MonBrightnessUp'),
    Key('MonBrightnessDown'),
    Key('KeyboardLightOnOff'),
    Key('KeyboardBrightnessUp'),
    Key('KeyboardBrightnessDown'),
    Key('PowerOff'),
    Key('WakeUp'),
    Key('Eject'),
    Key('ScreenSaver'),
    Key('WWW'),
    Key('Memo'),
    Key('LightBulb'),
    Key('Shop'),
    Key('History'),
    Key('AddFavorite'),
    Key('HotLinks'),
    Key('BrightnessAdjust'),
    Key('Finance'),
    Key('Community'),
    Key('AudioRewind'),  # Media rewind
    Key('BackForward'),
    Key('ApplicationLeft'),
    Key('ApplicationRight'),
    Key('Book'),
    Key('CD'),
    Key('Calculator'),
    Key('ToDoList'),
    Key('ClearGrab'),
    Key('Close'),
    Key('Copy'),
    Key('Cut'),
    Key('Display'),  # Output switch key
    Key('DOS'),
    Key('Documents'),
    Key('Excel'),
    Key('Explorer'),
    Key('Game'),
    Key('Go'),
    Key('iTouch'),
    Key('LogOff'),
    Key('Market'),
    Key('Meeting'),
    Key('MenuKB'),
    Key('MenuPB'),
    Key('MySites'),
    Key('News'),
    Key('OfficeHome'),
    Key('Option'),
    Key('Paste'),
    Key('Phone'),
    Key('Calendar'),
    Key('Reply'),
    Key('Reload'),
    Key('RotateWindows'),
    Key('RotationPB'),
    Key('RotationKB'),
    Key('Save'),
    Key('Send'),
    Key('Spell'),
    Key('SplitScreen'),
    Key('Support'),
    Key('TaskPane'),
    Key('Terminal'),
    Key('Tools'),
    Key('Travel'),
    Key('Video'),
    Key('Word'),
    Key('Xfer'),
    Key('ZoomIn'),
    Key('ZoomOut'),
    Key('Away'),
    Key('Messenger'),
    Key('WebCam'),
    Key('MailForward'),
    Key('Pictures'),
    Key('Music'),
    Key('Battery'),
    Key('Bluetooth'),
    Key('WLAN'),
    Key('UWB'),
    Key('AudioForward'),  # Media fast-forward
    Key('AudioRepeat'),  # Toggle repeat mode
    Key('AudioRandomPlay'),  # Toggle shuffle mode
    Key('Subtitle'),
    Key('AudioCycleTrack'),
    Key('Time'),
    Key('Hibernate'),
    Key('View'),
    Key('TopMenu'),
    Key('PowerDown'),
    Key('Suspend'),
    Key('ContrastAdjust'),

    Key('LaunchG'),
    Key('LaunchH'),

    Key('TouchpadToggle'),
    Key('TouchpadOn'),
    Key('TouchpadOff'),

    Key('MicMute'),

    Key('Red'),
    Key('Green'),
    Key('Yellow'),
    Key('Blue'),

    Key('ChannelUp'),
    Key('ChannelDown'),

    Key('Guide'),
    Key('Info'),
    Key('Settings'),

    Key('MicVolumeUp'),
    Key('MicVolumeDown'),

    Key('New'),
    Key('Open'),
    Key('Find'),
    Key('Undo'),
    Key('Redo'),

    Key('MediaLast'),

    ### Keypad navigation keys
    Key('Select'),
    Key('Yes'),
    Key('No'),

    ### Newer misc keys
    Key('Cancel'),
    Key('Printer'),
    Key('Execute'),
    Key('Sleep'),
    Key('Play'),  # Not the same as Key_MediaPlay
    Key('Zoom'),
    # Key('Jisho'),  # IME: Dictionary key
    # Key('Oyayubi_Left'),  # IME: Left Oyayubi key
    # Key('Oyayubi_Right'),  # IME: Right Oyayubi key
    Key('Exit'),

    # Device keys
    Key('Context1'),
    Key('Context2'),
    Key('Context3'),
    Key('Context4'),
    Key('Call'),  # set absolute state to in a call (do not toggle state)
    Key('Hangup'),  # set absolute state to hang up (do not toggle state)
    Key('Flip'),
    Key('ToggleCallHangup'),  # a toggle key for answering, or hanging up, based on current call state
    Key('VoiceDial'),
    Key('LastNumberRedial'),

    Key('Camera'),
    Key('CameraFocus'),

    Key('unknown'),
]
