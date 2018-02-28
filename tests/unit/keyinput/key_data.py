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
    uppertext = attr.ib('')
    member = attr.ib(None)


# From enum Key in qt5/qtbase/src/corelib/global/qnamespace.h
KEYS = [
    ### misc keys
    Key('Escape'),  # qutebrowser has a different name from Qt
    Key('Tab'),
    Key('Backtab', 'Tab'),  # qutebrowser has a different name from Qt
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
    Key('Super_L', 'Super L'),
    Key('Super_R', 'Super R'),
    Key('Menu'),
    Key('Hyper_L', 'Hyper L'),
    Key('Hyper_R', 'Hyper R'),
    Key('Help'),
    Key('Direction_L', 'Direction L'),
    Key('Direction_R', 'Direction R'),
    ### 7 bit printable ASCII
    Key('Space', text=' ', uppertext=' '),
    Key('Any', 'Space', text=' ', uppertext=' '),  # Same value
    Key('Exclam', '!', text='!', uppertext='!'),
    Key('QuoteDbl', '"', text='"', uppertext='"'),
    Key('NumberSign', '#', text='#', uppertext='#'),
    Key('Dollar', '$', text='$', uppertext='$'),
    Key('Percent', '%', text='%', uppertext='%'),
    Key('Ampersand', '&', text='&', uppertext='&'),
    Key('Apostrophe', "'", text="'", uppertext="'"),
    Key('ParenLeft', '(', text='(', uppertext='('),
    Key('ParenRight', ')', text=')', uppertext=')'),
    Key('Asterisk', '*', text='*', uppertext='*'),
    Key('Plus', '+', text='+', uppertext='+'),
    Key('Comma', ',', text=',', uppertext=','),
    Key('Minus', '-', text='-', uppertext='-'),
    Key('Period', '.', text='.', uppertext='.'),
    Key('Slash', '/', text='/', uppertext='/'),
    Key('0', text='0', uppertext='0'),
    Key('1', text='1', uppertext='1'),
    Key('2', text='2', uppertext='2'),
    Key('3', text='3', uppertext='3'),
    Key('4', text='4', uppertext='4'),
    Key('5', text='5', uppertext='5'),
    Key('6', text='6', uppertext='6'),
    Key('7', text='7', uppertext='7'),
    Key('8', text='8', uppertext='8'),
    Key('9', text='9', uppertext='9'),
    Key('Colon', ':', text=':', uppertext=':'),
    Key('Semicolon', ';', text=';', uppertext=';'),
    Key('Less', '<', text='<', uppertext='<'),
    Key('Equal', '=', text='=', uppertext='='),
    Key('Greater', '>', text='>', uppertext='>'),
    Key('Question', '?', text='?', uppertext='?'),
    Key('At', '@', text='@', uppertext='@'),
    Key('A', text='a', uppertext='A'),
    Key('B', text='b', uppertext='B'),
    Key('C', text='c', uppertext='C'),
    Key('D', text='d', uppertext='D'),
    Key('E', text='e', uppertext='E'),
    Key('F', text='f', uppertext='F'),
    Key('G', text='g', uppertext='G'),
    Key('H', text='h', uppertext='H'),
    Key('I', text='i', uppertext='I'),
    Key('J', text='j', uppertext='J'),
    Key('K', text='k', uppertext='K'),
    Key('L', text='l', uppertext='L'),
    Key('M', text='m', uppertext='M'),
    Key('N', text='n', uppertext='N'),
    Key('O', text='o', uppertext='O'),
    Key('P', text='p', uppertext='P'),
    Key('Q', text='q', uppertext='Q'),
    Key('R', text='r', uppertext='R'),
    Key('S', text='s', uppertext='S'),
    Key('T', text='t', uppertext='T'),
    Key('U', text='u', uppertext='U'),
    Key('V', text='v', uppertext='V'),
    Key('W', text='w', uppertext='W'),
    Key('X', text='x', uppertext='X'),
    Key('Y', text='y', uppertext='Y'),
    Key('Z', text='z', uppertext='Z'),
    Key('BracketLeft', '[', text='[', uppertext='['),
    Key('Backslash', '\\', text='\\', uppertext='\\'),
    Key('BracketRight', ']', text=']', uppertext=']'),
    Key('AsciiCircum', '^', text='^', uppertext='^'),
    Key('Underscore', '_', text='_', uppertext='_'),
    Key('QuoteLeft', '`', text='`', uppertext='`'),
    Key('BraceLeft', '{', text='{', uppertext='{'),
    Key('Bar', '|', text='|', uppertext='|'),
    Key('BraceRight', '}', text='}', uppertext='}'),
    Key('AsciiTilde', '~', text='~', uppertext='~'),

    Key('nobreakspace', ' ', text=' ', uppertext=' '),
    Key('exclamdown', '¡', text='¡', uppertext='¡'),
    Key('cent', '¢', text='¢', uppertext='¢'),
    Key('sterling', '£', text='£', uppertext='£'),
    Key('currency', '¤', text='¤', uppertext='¤'),
    Key('yen', '¥', text='¥', uppertext='¥'),
    Key('brokenbar', '¦', text='¦', uppertext='¦'),
    Key('section', '§', text='§', uppertext='§'),
    Key('diaeresis', '¨', text='¨', uppertext='¨'),
    Key('copyright', '©', text='©', uppertext='©'),
    Key('ordfeminine', 'ª', text='ª', uppertext='ª'),
    Key('guillemotleft', '«', text='«', uppertext='«'),
    Key('notsign', '¬', text='¬', uppertext='¬'),
    Key('hyphen', '­', text='­', uppertext='­'),
    Key('registered', '®', text='®', uppertext='®'),
    Key('macron', '¯', text='¯', uppertext='¯'),
    Key('degree', '°', text='°', uppertext='°'),
    Key('plusminus', '±', text='±', uppertext='±'),
    Key('twosuperior', '²', text='²', uppertext='²'),
    Key('threesuperior', '³', text='³', uppertext='³'),
    Key('acute', '´', text='´', uppertext='´'),
    Key('mu', 'Μ', text='μ', uppertext='Μ'),
    Key('paragraph', '¶', text='¶', uppertext='¶'),
    Key('periodcentered', '·', text='·', uppertext='·'),
    Key('cedilla', '¸', text='¸', uppertext='¸'),
    Key('onesuperior', '¹', text='¹', uppertext='¹'),
    Key('masculine', 'º', text='º', uppertext='º'),
    Key('guillemotright', '»', text='»', uppertext='»'),
    Key('onequarter', '¼', text='¼', uppertext='¼'),
    Key('onehalf', '½', text='½', uppertext='½'),
    Key('threequarters', '¾', text='¾', uppertext='¾'),
    Key('questiondown', '¿', text='¿', uppertext='¿'),
    Key('Agrave', 'À', text='à', uppertext='À'),
    Key('Aacute', 'Á', text='á', uppertext='Á'),
    Key('Acircumflex', 'Â', text='â', uppertext='Â'),
    Key('Atilde', 'Ã', text='ã', uppertext='Ã'),
    Key('Adiaeresis', 'Ä', text='ä', uppertext='Ä'),
    Key('Aring', 'Å', text='å', uppertext='Å'),
    Key('AE', 'Æ', text='æ', uppertext='Æ'),
    Key('Ccedilla', 'Ç', text='ç', uppertext='Ç'),
    Key('Egrave', 'È', text='è', uppertext='È'),
    Key('Eacute', 'É', text='é', uppertext='É'),
    Key('Ecircumflex', 'Ê', text='ê', uppertext='Ê'),
    Key('Ediaeresis', 'Ë', text='ë', uppertext='Ë'),
    Key('Igrave', 'Ì', text='ì', uppertext='Ì'),
    Key('Iacute', 'Í', text='í', uppertext='Í'),
    Key('Icircumflex', 'Î', text='î', uppertext='Î'),
    Key('Idiaeresis', 'Ï', text='ï', uppertext='Ï'),
    Key('ETH', 'Ð', text='ð', uppertext='Ð'),
    Key('Ntilde', 'Ñ', text='ñ', uppertext='Ñ'),
    Key('Ograve', 'Ò', text='ò', uppertext='Ò'),
    Key('Oacute', 'Ó', text='ó', uppertext='Ó'),
    Key('Ocircumflex', 'Ô', text='ô', uppertext='Ô'),
    Key('Otilde', 'Õ', text='õ', uppertext='Õ'),
    Key('Odiaeresis', 'Ö', text='ö', uppertext='Ö'),
    Key('multiply', '×', text='×', uppertext='×'),
    Key('Ooblique', 'Ø', text='ø', uppertext='Ø'),
    Key('Ugrave', 'Ù', text='ù', uppertext='Ù'),
    Key('Uacute', 'Ú', text='ú', uppertext='Ú'),
    Key('Ucircumflex', 'Û', text='û', uppertext='Û'),
    Key('Udiaeresis', 'Ü', text='ü', uppertext='Ü'),
    Key('Yacute', 'Ý', text='ý', uppertext='Ý'),
    Key('THORN', 'Þ', text='þ', uppertext='Þ'),
    Key('ssharp', 'ß', text='ß', uppertext='ß'),
    Key('division', '÷', text='÷', uppertext='÷'),
    Key('ydiaeresis', 'Ÿ', text='ÿ', uppertext='Ÿ'),

    ### International input method support (X keycode - 0xEE00, the
    ### definition follows Qt/Embedded 2.3.7) Only interesting if
    ### you are writing your own input method

    ### International & multi-key character composition
    Key('AltGr'),
    Key('Multi_key', 'Multi key'),  # Multi-key character compose
    Key('Codeinput', 'Code input'),
    Key('SingleCandidate', 'Single Candidate'),
    Key('MultipleCandidate', 'Multiple Candidate'),
    Key('PreviousCandidate', 'Previous Candidate'),

    ### Misc Functions
    Key('Mode_switch', 'Mode switch'),  # Character set switch
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
    Key('Dead_Grave', '`'),
    Key('Dead_Acute', '´'),
    Key('Dead_Circumflex', '^'),
    Key('Dead_Tilde', '~'),
    Key('Dead_Macron', '¯'),
    Key('Dead_Breve', '˘'),
    Key('Dead_Abovedot', '˙'),
    Key('Dead_Diaeresis', '¨'),
    Key('Dead_Abovering', '˚'),
    Key('Dead_Doubleacute', '˝'),
    Key('Dead_Caron', 'ˇ'),
    Key('Dead_Cedilla', '¸'),
    Key('Dead_Ogonek', '˛'),
    Key('Dead_Iota', 'Iota'),
    Key('Dead_Voiced_Sound', 'Voiced Sound'),
    Key('Dead_Semivoiced_Sound', 'Semivoiced Sound'),
    Key('Dead_Belowdot', 'Belowdot'),
    Key('Dead_Hook', 'Hook'),
    Key('Dead_Horn', 'Horn'),

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
    Key('Launch0', 'Launch (0)'),
    Key('Launch1', 'Launch (1)'),
    Key('Launch2', 'Launch (2)'),
    Key('Launch3', 'Launch (3)'),
    Key('Launch4', 'Launch (4)'),
    Key('Launch5', 'Launch (5)'),
    Key('Launch6', 'Launch (6)'),
    Key('Launch7', 'Launch (7)'),
    Key('Launch8', 'Launch (8)'),
    Key('Launch9', 'Launch (9)'),
    Key('LaunchA', 'Launch (A)'),
    Key('LaunchB', 'Launch (B)'),
    Key('LaunchC', 'Launch (C)'),
    Key('LaunchD', 'Launch (D)'),
    Key('LaunchE', 'Launch (E)'),
    Key('LaunchF', 'Launch (F)'),
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
    Key('Memo', 'Memo'),
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
    Key('ToDoList', 'To Do List'),
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
    Key('Calendar'),
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
    Key('ContrastAdjust', 'Contrast Adjust'),

    Key('LaunchG', 'Launch (G)'),
    Key('LaunchH', 'Launch (H)'),

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

    Key('MediaLast', 'Media Last'),

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

    Key('unknown', 'Unknown'),
]
