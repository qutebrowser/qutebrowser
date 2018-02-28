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
    Key('Escape', 'Esc'),
    Key('Tab'),
    Key('Backtab'),
    Key('Backspace'),
    Key('Return'),
    Key('Enter'),
    Key('Insert', 'Ins'),
    Key('Delete', 'Del'),
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
    Key('PageUp', 'PgUp'),
    Key('PageDown', 'PgDown'),
    ### modifiers
    Key('Shift', '\u17c0\udc20'),  # FIXME
    Key('Control', '\u17c0\udc21'),  # FIXME
    Key('Meta', '\u17c0\udc22'),  # FIXME
    Key('Alt', '\u17c0\udc23'),  # FIXME
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
    Key('Super_L', '\u17c0\udc53'),  # FIXME
    Key('Super_R', '\u17c0\udc54'),  # FIXME
    Key('Menu'),
    Key('Hyper_L', '\u17c0\udc56'),  # FIXME
    Key('Hyper_R', '\u17c0\udc57'),  # FIXME
    Key('Help'),
    Key('Direction_L', '\u17c0\udc59'),  # FIXME
    Key('Direction_R', '\u17c0\udc60'),  # FIXME
    ### 7 bit printable ASCII
    Key('Space'),
    Key('Any', 'Space'),  # FIXME
    Key('Exclam', '!'),
    Key('QuoteDbl', '"'),
    Key('NumberSign', '#'),
    Key('Dollar', '$'),
    Key('Percent', '%'),
    Key('Ampersand', '&'),
    Key('Apostrophe', "'"),
    Key('ParenLeft', '('),
    Key('ParenRight', '),')
    Key('Asterisk', '*'),
    Key('Plus', '+'),
    Key('Comma', ','),
    Key('Minus', '-'),
    Key('Period', '.'),
    Key('Slash', '/'),
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
    Key('Colon', ':'),
    Key('Semicolon', ';'),
    Key('Less', '<'),
    Key('Equal', '='),
    Key('Greater', '>'),
    Key('Question', '?'),
    Key('At', '@'),
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
    Key('BracketLeft', '['),
    Key('Backslash', '\\'),
    Key('BracketRight', ']'),
    Key('AsciiCircum', '^'),
    Key('Underscore', '_'),
    Key('QuoteLeft', '`'),
    Key('BraceLeft', '{'),
    Key('Bar', '|'),
    Key('BraceRight', '}'),
    Key('AsciiTilde', '~'),

    Key('nobreakspace', ' '),
    Key('exclamdown', '¡'),
    Key('cent', '¢'),
    Key('sterling', '£'),
    Key('currency', '¤'),
    Key('yen', '¥'),
    Key('brokenbar', '¦'),
    Key('section', '§'),
    Key('diaeresis', '¨'),
    Key('copyright', '©'),
    Key('ordfeminine', 'ª'),
    Key('guillemotleft', '«'),
    Key('notsign', '¬'),
    Key('hyphen', '­'),
    Key('registered', '®'),
    Key('macron', '¯'),
    Key('degree', '°'),
    Key('plusminus', '±'),
    Key('twosuperior', '²'),
    Key('threesuperior', '³'),
    Key('acute', '´'),
    Key('mu', 'Μ'),
    Key('paragraph', '¶'),
    Key('periodcentered', '·'),
    Key('cedilla', '¸'),
    Key('onesuperior', '¹'),
    Key('masculine', 'º'),
    Key('guillemotright', '»'),
    Key('onequarter', '¼'),
    Key('onehalf', '½'),
    Key('threequarters', '¾'),
    Key('questiondown', '¿'),
    Key('Agrave', 'À'),
    Key('Aacute', 'Á'),
    Key('Acircumflex', 'Â'),
    Key('Atilde', 'Ã'),
    Key('Adiaeresis', 'Ä'),
    Key('Aring', 'Å'),
    Key('AE', 'Æ'),
    Key('Ccedilla', 'Ç'),
    Key('Egrave', 'È'),
    Key('Eacute', 'É'),
    Key('Ecircumflex', 'Ê'),
    Key('Ediaeresis', 'Ë'),
    Key('Igrave', 'Ì'),
    Key('Iacute', 'Í'),
    Key('Icircumflex', 'Î'),
    Key('Idiaeresis', 'Ï'),
    Key('ETH', 'Ð'),
    Key('Ntilde', 'Ñ'),
    Key('Ograve', 'Ò'),
    Key('Oacute', 'Ó'),
    Key('Ocircumflex', 'Ô'),
    Key('Otilde', 'Õ'),
    Key('Odiaeresis', 'Ö'),
    Key('multiply', '×'),
    Key('Ooblique', 'Ø'),
    Key('Ugrave', 'Ù'),
    Key('Uacute', 'Ú'),
    Key('Ucircumflex', 'Û'),
    Key('Udiaeresis', 'Ü'),
    Key('Yacute', 'Ý'),
    Key('THORN', 'Þ'),
    Key('ssharp', 'ß'),
    Key('division', '÷'),
    Key('ydiaeresis', 'Ÿ'),

    ### International input method support (X keycode - 0xEE00, the
    ### definition follows Qt/Embedded 2.3.7) Only interesting if
    ### you are writing your own input method

    ### International & multi-key character composition
    Key('AltGr', '\u17c4\udd03'),  # FIXME
    Key('Multi_key', '\u17c4\udd20'),  # FIXME Multi-key character compose
    Key('Codeinput', 'Code input'),
    Key('SingleCandidate', '\u17c4\udd3c'),  # FIXME
    Key('MultipleCandidate', 'Multiple Candidate'),
    Key('PreviousCandidate', 'Previous Candidate'),
    Key('Mode_switch', '\u17c4\udd7e'),  # FIXME

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
    Key('Hiragana_Katakana', 'Hiragana Katakana'),  # Hiragana/Katakana toggle
    Key('Zenkaku'),  # to Zenkaku
    Key('Hankaku'),  # to Hankaku
    Key('Zenkaku_Hankaku', 'Zenkaku Hankaku'),  # Zenkaku/Hankaku toggle
    Key('Touroku'),  # Add to Dictionary
    Key('Massyo'),  # Delete from Dictionary
    Key('Kana_Lock', 'Kana Lock'),
    Key('Kana_Shift', 'Kana Shift'),
    Key('Eisu_Shift', 'Eisu Shift'),  # Alphanumeric Shift
    Key('Eisu_toggle', 'Eisu toggle'),  # Alphanumeric toggle
    # Key('Kanji_Bangou'),  # Codeinput
    # Key('Zen_Koho'),  # Multiple/All Candidate(s)
    # Key('Mae_Koho'),  # Previous Candidate

    ### Korean keyboard support
    ###
    ### In fact, many Korean users need only 2 keys, Key_Hangul and
    ### Key_Hangul_Hanja. But rest of the keys are good for future.

    Key('Hangul'),  # Hangul start/stop(toggle),
    Key('Hangul_Start', 'Hangul Start'),  # Hangul start
    Key('Hangul_End', 'Hangul End'),  # Hangul end, English start
    Key('Hangul_Hanja', 'Hangul Hanja'),  # Start Hangul->Hanja Conversion
    Key('Hangul_Jamo', 'Hangul Jamo'),  # Hangul Jamo mode
    Key('Hangul_Romaja', 'Hangul Romaja'),  # Hangul Romaja mode
    # Key('Hangul_Codeinput', 'Hangul Codeinput'),# Hangul code input mode
    Key('Hangul_Jeonja', 'Hangul Jeonja'),  # Jeonja mode
    Key('Hangul_Banja', 'Hangul Banja'),  # Banja mode
    Key('Hangul_PreHanja', 'Hangul PreHanja'),  # Pre Hanja conversion
    Key('Hangul_PostHanja', 'Hangul PostHanja'),  # Post Hanja conversion
    # Key('Hangul_SingleCandidate', 'Hangul SingleCandidate'),  # Single candidate
    # Key('Hangul_MultipleCandidate', 'Hangul MultipleCandidate'),  # Multiple candidate
    # Key('Hangul_PreviousCandidate', 'Hangul PreviousCandidate'),  # Previous candidate
    Key('Hangul_Special', 'Hangul Special'),  # Special symbols
    # Key('Hangul_switch', 'Hangul switch'),  # Alias for mode_switch

    # dead keys (X keycode - 0xED00 to avoid the conflict),
    Key('Dead_Grave', '\u17c4\ude50'),  # FIXME
    Key('Dead_Acute', '\u17c4\ude51'),  # FIXME
    Key('Dead_Circumflex', '\u17c4\ude52'),  # FIXME
    Key('Dead_Tilde', '\u17c4\ude53'),  # FIXME
    Key('Dead_Macron', '\u17c4\ude54'),  # FIXME
    Key('Dead_Breve', '\u17c4\ude55'),  # FIXME
    Key('Dead_Abovedot', '\u17c4\ude56'),  # FIXME
    Key('Dead_Diaeresis', '\u17c4\ude57'),  # FIXME
    Key('Dead_Abovering', '\u17c4\ude58'),  # FIXME
    Key('Dead_Doubleacute', '\u17c4\ude59'),  # FIXME
    Key('Dead_Caron', '\u17c4\ude5a'),  # FIXME
    Key('Dead_Cedilla', '\u17c4\ude5b'),  # FIXME
    Key('Dead_Ogonek', '\u17c4\ude5c'),  # FIXME
    Key('Dead_Iota', '\u17c4\ude5d'),  # FIXME
    Key('Dead_Voiced_Sound', '\u17c4\ude5e'),  # FIXME
    Key('Dead_Semivoiced_Sound', '\u17c4\ude5f'),  # FIXME
    Key('Dead_Belowdot', '\u17c4\ude60'),  # FIXME
    Key('Dead_Hook', '\u17c4\ude61'),  # FIXME
    Key('Dead_Horn', '\u17c4\ude62'),  # FIXME

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
    Key('VolumeDown', 'Volume Down'),
    Key('VolumeMute', 'Volume Mute'),
    Key('VolumeUp', 'Volume Up'),
    Key('BassBoost', 'Bass Boost'),
    Key('BassUp', 'Bass Up'),
    Key('BassDown', 'Bass Down'),
    Key('TrebleUp', 'Treble Up'),
    Key('TrebleDown', 'Treble Down'),
    Key('MediaPlay', 'Media Play'),
    Key('MediaStop', 'Media Stop'),
    Key('MediaPrevious', 'Media Previous'),
    Key('MediaNext', 'Media Next'),
    Key('MediaRecord', 'Media Record'),
    Key('MediaPause', 'Media Pause'),
    Key('MediaTogglePlayPause', 'Toggle Media Play/Pause'),
    Key('HomePage', 'Home Page'),
    Key('Favorites'),
    Key('Search'),
    Key('Standby'),

    Key('OpenUrl', 'Open URL'),
    Key('LaunchMail', 'Launch Mail'),
    Key('LaunchMedia', 'Launch Media'),
    Key('Launch0', 'Launch (0),')
    Key('Launch1', 'Launch (1),')
    Key('Launch2', 'Launch (2),')
    Key('Launch3', 'Launch (3),')
    Key('Launch4', 'Launch (4),')
    Key('Launch5', 'Launch (5),')
    Key('Launch6', 'Launch (6),')
    Key('Launch7', 'Launch (7),')
    Key('Launch8', 'Launch (8),')
    Key('Launch9', 'Launch (9),')
    Key('LaunchA', 'Launch (A),')
    Key('LaunchB', 'Launch (B),')
    Key('LaunchC', 'Launch (C),')
    Key('LaunchD', 'Launch (D),')
    Key('LaunchE', 'Launch (E),')
    Key('LaunchF', 'Launch (F),')
    Key('MonBrightnessUp', 'Monitor Brightness Up'),
    Key('MonBrightnessDown', 'Monitor Brightness Down'),
    Key('KeyboardLightOnOff', 'Keyboard Light On/Off'),
    Key('KeyboardBrightnessUp', 'Keyboard Brightness Up'),
    Key('KeyboardBrightnessDown', 'Keyboard Brightness Down'),
    Key('PowerOff', 'Power Off'),
    Key('WakeUp', 'Wake Up'),
    Key('Eject'),
    Key('ScreenSaver', 'Screensaver'),
    Key('WWW'),
    Key('Memo', '\u17c0\udcbc'),  # FIXME
    Key('LightBulb'),
    Key('Shop'),
    Key('History'),
    Key('AddFavorite', 'Add Favorite'),
    Key('HotLinks', 'Hot Links'),
    Key('BrightnessAdjust', 'Adjust Brightness'),
    Key('Finance'),
    Key('Community'),
    Key('AudioRewind', 'Media Rewind'),
    Key('BackForward', 'Back Forward'),
    Key('ApplicationLeft', 'Application Left'),
    Key('ApplicationRight', 'Application Right'),
    Key('Book'),
    Key('CD'),
    Key('Calculator'),
    Key('ToDoList', '\u17c0\udccc'),  # FIXME
    Key('ClearGrab', 'Clear Grab'),
    Key('Close'),
    Key('Copy'),
    Key('Cut'),
    Key('Display'),  # Output switch key
    Key('DOS'),
    Key('Documents'),
    Key('Excel', 'Spreadsheet'),
    Key('Explorer', 'Browser'),
    Key('Game'),
    Key('Go'),
    Key('iTouch'),
    Key('LogOff', 'Logoff'),
    Key('Market'),
    Key('Meeting'),
    Key('MenuKB', 'Keyboard Menu'),
    Key('MenuPB', 'Menu PB'),
    Key('MySites', 'My Sites'),
    Key('News'),
    Key('OfficeHome', 'Home Office'),
    Key('Option'),
    Key('Paste'),
    Key('Phone'),
    Key('Calendar', '\u17c0\udce4'),  # FIXME
    Key('Reply'),
    Key('Reload'),
    Key('RotateWindows', 'Rotate Windows'),
    Key('RotationPB', 'Rotation PB'),
    Key('RotationKB', 'Rotation KB'),
    Key('Save'),
    Key('Send'),
    Key('Spell', 'Spellchecker'),
    Key('SplitScreen', 'Split Screen'),
    Key('Support'),
    Key('TaskPane', 'Task Panel'),
    Key('Terminal'),
    Key('Tools'),
    Key('Travel'),
    Key('Video'),
    Key('Word', 'Word Processor'),
    Key('Xfer', 'XFer'),
    Key('ZoomIn', 'Zoom In'),
    Key('ZoomOut', 'Zoom Out'),
    Key('Away'),
    Key('Messenger'),
    Key('WebCam'),
    Key('MailForward', 'Mail Forward'),
    Key('Pictures'),
    Key('Music'),
    Key('Battery'),
    Key('Bluetooth'),
    Key('WLAN', 'Wireless'),
    Key('UWB', 'Ultra Wide Band'),
    Key('AudioForward', 'Media Fast Forward'),
    Key('AudioRepeat', 'Audio Repeat'),  # Toggle repeat mode
    Key('AudioRandomPlay', 'Audio Random Play'),  # Toggle shuffle mode
    Key('Subtitle'),
    Key('AudioCycleTrack', 'Audio Cycle Track'),
    Key('Time'),
    Key('Hibernate'),
    Key('View'),
    Key('TopMenu', 'Top Menu'),
    Key('PowerDown', 'Power Down'),
    Key('Suspend'),
    Key('ContrastAdjust', '\u17c0\udd0d'),  # FIXME

    Key('LaunchG', '\u17c0\udd0e'),  # FIXME
    Key('LaunchH', '\u17c0\udd0f'),  # FIXME

    Key('TouchpadToggle', 'Touchpad Toggle'),
    Key('TouchpadOn', 'Touchpad On'),
    Key('TouchpadOff', 'Touchpad Off'),

    Key('MicMute', 'Microphone Mute'),

    Key('Red'),
    Key('Green'),
    Key('Yellow'),
    Key('Blue'),

    Key('ChannelUp', 'Channel Up'),
    Key('ChannelDown', 'Channel Down'),

    Key('Guide'),
    Key('Info'),
    Key('Settings'),

    Key('MicVolumeUp', 'Microphone Volume Up'),
    Key('MicVolumeDown', 'Microphone Volume Down'),

    Key('New'),
    Key('Open'),
    Key('Find'),
    Key('Undo'),
    Key('Redo'),

    Key('MediaLast', '\u17ff\udfff'),  # FIXME

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
    Key('ToggleCallHangup', 'Toggle Call/Hangup'),  # a toggle key for answering, or hanging up, based on current call state
    Key('VoiceDial', 'Voice Dial'),
    Key('LastNumberRedial', 'Last Number Redial'),

    Key('Camera', 'Camera Shutter'),
    Key('CameraFocus', 'Camera Focus'),

    Key('unknown', ''),  # FIXME
]
