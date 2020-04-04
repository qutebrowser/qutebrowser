# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=line-too-long


"""Data used by test_keyutils.py to test all keys."""


import attr
from PyQt5.QtCore import Qt


@attr.s
class Key:

    """A key with expected values.

    Attributes:
        attribute: The name of the Qt::Key attribute ('Foo' -> Qt.Key_Foo)
        name: The name returned by str(KeyInfo) with that key.
        text: The text returned by KeyInfo.text().
        uppertext: The text returned by KeyInfo.text() with shift.
        member: The numeric value.
    """

    attribute = attr.ib()
    name = attr.ib(None)
    text = attr.ib('')
    uppertext = attr.ib('')
    member = attr.ib(None)
    qtest = attr.ib(True)

    def __attrs_post_init__(self):
        if self.attribute:
            self.member = getattr(Qt, 'Key_' + self.attribute, None)
        if self.name is None:
            self.name = self.attribute


@attr.s
class Modifier:

    """A modifier with expected values.

    Attributes:
        attribute: The name of the Qt::KeyboardModifier attribute
                   ('Shift' -> Qt.ShiftModifier)
        name: The name returned by str(KeyInfo) with that modifier.
        member: The numeric value.
    """

    attribute = attr.ib()
    name = attr.ib(None)
    member = attr.ib(None)

    def __attrs_post_init__(self):
        self.member = getattr(Qt, self.attribute + 'Modifier')
        if self.name is None:
            self.name = self.attribute


# From enum Key in qt5/qtbase/src/corelib/global/qnamespace.h
KEYS = [
    ### misc keys
    Key('Escape', text='\x1b', uppertext='\x1b'),
    Key('Tab', text='\t', uppertext='\t'),
    Key('Backtab', qtest=False),  # Qt assumes VT (vertical tab)
    Key('Backspace', text='\b', uppertext='\b'),
    Key('Return', text='\r', uppertext='\r'),
    Key('Enter', text='\r', uppertext='\r'),
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
    Key('mu', 'Μ', text='μ', uppertext='Μ', qtest=False),  # Qt assumes U+00B5 instead of U+03BC
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
    Key('AltGr', qtest=False),
    Key('Multi_key', 'Multi key', qtest=False),  # Multi-key character compose
    Key('Codeinput', 'Code input', qtest=False),
    Key('SingleCandidate', 'Single Candidate', qtest=False),
    Key('MultipleCandidate', 'Multiple Candidate', qtest=False),
    Key('PreviousCandidate', 'Previous Candidate', qtest=False),

    ### Misc Functions
    Key('Mode_switch', 'Mode switch', qtest=False),  # Character set switch
    # Key('script_switch'),  # Alias for mode_switch

    ### Japanese keyboard support
    Key('Kanji', qtest=False),  # Kanji, Kanji convert
    Key('Muhenkan', qtest=False),  # Cancel Conversion
    # Key('Henkan_Mode', qtest=False),  # Start/Stop Conversion
    Key('Henkan', qtest=False),  # Alias for Henkan_Mode
    Key('Romaji', qtest=False),  # to Romaji
    Key('Hiragana', qtest=False),  # to Hiragana
    Key('Katakana', qtest=False),  # to Katakana
    Key('Hiragana_Katakana', 'Hiragana Katakana', qtest=False),  # Hiragana/Katakana toggle
    Key('Zenkaku', qtest=False),  # to Zenkaku
    Key('Hankaku', qtest=False),  # to Hankaku
    Key('Zenkaku_Hankaku', 'Zenkaku Hankaku', qtest=False),  # Zenkaku/Hankaku toggle
    Key('Touroku', qtest=False),  # Add to Dictionary
    Key('Massyo', qtest=False),  # Delete from Dictionary
    Key('Kana_Lock', 'Kana Lock', qtest=False),
    Key('Kana_Shift', 'Kana Shift', qtest=False),
    Key('Eisu_Shift', 'Eisu Shift', qtest=False),  # Alphanumeric Shift
    Key('Eisu_toggle', 'Eisu toggle', qtest=False),  # Alphanumeric toggle
    # Key('Kanji_Bangou', qtest=False),  # Codeinput
    # Key('Zen_Koho', qtest=False),  # Multiple/All Candidate(s)
    # Key('Mae_Koho', qtest=False),  # Previous Candidate

    ### Korean keyboard support
    ###
    ### In fact, many users from Korea need only 2 keys, Key_Hangul and
    ### Key_Hangul_Hanja. But rest of the keys are good for future.

    Key('Hangul', qtest=False),  # Hangul start/stop(toggle),
    Key('Hangul_Start', 'Hangul Start', qtest=False),  # Hangul start
    Key('Hangul_End', 'Hangul End', qtest=False),  # Hangul end, English start
    Key('Hangul_Hanja', 'Hangul Hanja', qtest=False),  # Start Hangul->Hanja Conversion
    Key('Hangul_Jamo', 'Hangul Jamo', qtest=False),  # Hangul Jamo mode
    Key('Hangul_Romaja', 'Hangul Romaja', qtest=False),  # Hangul Romaja mode
    # Key('Hangul_Codeinput', 'Hangul Codeinput', qtest=False),# Hangul code input mode
    Key('Hangul_Jeonja', 'Hangul Jeonja', qtest=False),  # Jeonja mode
    Key('Hangul_Banja', 'Hangul Banja', qtest=False),  # Banja mode
    Key('Hangul_PreHanja', 'Hangul PreHanja', qtest=False),  # Pre Hanja conversion
    Key('Hangul_PostHanja', 'Hangul PostHanja', qtest=False),  # Post Hanja conversion
    # Key('Hangul_SingleCandidate', 'Hangul SingleCandidate', qtest=False),  # Single candidate
    # Key('Hangul_MultipleCandidate', 'Hangul MultipleCandidate', qtest=False),  # Multiple candidate
    # Key('Hangul_PreviousCandidate', 'Hangul PreviousCandidate', qtest=False),  # Previous candidate
    Key('Hangul_Special', 'Hangul Special', qtest=False),  # Special symbols
    # Key('Hangul_switch', 'Hangul switch', qtest=False),  # Alias for mode_switch

    # dead keys (X keycode - 0xED00 to avoid the conflict, qtest=False),
    Key('Dead_Grave', '`', qtest=False),
    Key('Dead_Acute', '´', qtest=False),
    Key('Dead_Circumflex', '^', qtest=False),
    Key('Dead_Tilde', '~', qtest=False),
    Key('Dead_Macron', '¯', qtest=False),
    Key('Dead_Breve', '˘', qtest=False),
    Key('Dead_Abovedot', '˙', qtest=False),
    Key('Dead_Diaeresis', '¨', qtest=False),
    Key('Dead_Abovering', '˚', qtest=False),
    Key('Dead_Doubleacute', '˝', qtest=False),
    Key('Dead_Caron', 'ˇ', qtest=False),
    Key('Dead_Cedilla', '¸', qtest=False),
    Key('Dead_Ogonek', '˛', qtest=False),
    Key('Dead_Iota', 'Iota', qtest=False),
    Key('Dead_Voiced_Sound', 'Voiced Sound', qtest=False),
    Key('Dead_Semivoiced_Sound', 'Semivoiced Sound', qtest=False),
    Key('Dead_Belowdot', 'Belowdot', qtest=False),
    Key('Dead_Hook', 'Hook', qtest=False),
    Key('Dead_Horn', 'Horn', qtest=False),

    Key('Dead_Stroke', '̵', qtest=False),
    Key('Dead_Abovecomma', '̓', qtest=False),
    Key('Dead_Abovereversedcomma', '̔', qtest=False),
    Key('Dead_Doublegrave', '̏', qtest=False),
    Key('Dead_Belowring', '̥', qtest=False),
    Key('Dead_Belowmacron', '̱', qtest=False),
    Key('Dead_Belowcircumflex', '̭', qtest=False),
    Key('Dead_Belowtilde', '̰', qtest=False),
    Key('Dead_Belowbreve', '̮', qtest=False),
    Key('Dead_Belowdiaeresis', '̤', qtest=False),
    Key('Dead_Invertedbreve', '̑', qtest=False),
    Key('Dead_Belowcomma', '̦', qtest=False),
    Key('Dead_Currency', '¤', qtest=False),
    Key('Dead_a', 'a', qtest=False),
    Key('Dead_A', 'A', qtest=False),
    Key('Dead_e', 'e', qtest=False),
    Key('Dead_E', 'E', qtest=False),
    Key('Dead_i', 'i', qtest=False),
    Key('Dead_I', 'I', qtest=False),
    Key('Dead_o', 'o', qtest=False),
    Key('Dead_O', 'O', qtest=False),
    Key('Dead_u', 'u', qtest=False),
    Key('Dead_U', 'U', qtest=False),
    Key('Dead_Small_Schwa', 'ə', qtest=False),
    Key('Dead_Capital_Schwa', 'Ə', qtest=False),
    Key('Dead_Greek', 'Greek', qtest=False),
    Key('Dead_Lowline', '̲', qtest=False),
    Key('Dead_Aboveverticalline', '̍', qtest=False),
    Key('Dead_Belowverticalline', '\u0329', qtest=False),
    Key('Dead_Longsolidusoverlay', '̸', qtest=False),

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
    Key('MediaPause', 'Media Pause', qtest=False),
    Key('MediaTogglePlayPause', 'Toggle Media Play/Pause', qtest=False),
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
    Key('MonBrightnessUp', 'Monitor Brightness Up', qtest=False),
    Key('MonBrightnessDown', 'Monitor Brightness Down', qtest=False),
    Key('KeyboardLightOnOff', 'Keyboard Light On/Off', qtest=False),
    Key('KeyboardBrightnessUp', 'Keyboard Brightness Up', qtest=False),
    Key('KeyboardBrightnessDown', 'Keyboard Brightness Down', qtest=False),
    Key('PowerOff', 'Power Off', qtest=False),
    Key('WakeUp', 'Wake Up', qtest=False),
    Key('Eject', qtest=False),
    Key('ScreenSaver', 'Screensaver', qtest=False),
    Key('WWW', qtest=False),
    Key('Memo', 'Memo', qtest=False),
    Key('LightBulb', qtest=False),
    Key('Shop', qtest=False),
    Key('History', qtest=False),
    Key('AddFavorite', 'Add Favorite', qtest=False),
    Key('HotLinks', 'Hot Links', qtest=False),
    Key('BrightnessAdjust', 'Adjust Brightness', qtest=False),
    Key('Finance', qtest=False),
    Key('Community', qtest=False),
    Key('AudioRewind', 'Media Rewind', qtest=False),
    Key('BackForward', 'Back Forward', qtest=False),
    Key('ApplicationLeft', 'Application Left', qtest=False),
    Key('ApplicationRight', 'Application Right', qtest=False),
    Key('Book', qtest=False),
    Key('CD', qtest=False),
    Key('Calculator', qtest=False),
    Key('ToDoList', 'To Do List', qtest=False),
    Key('ClearGrab', 'Clear Grab', qtest=False),
    Key('Close', qtest=False),
    Key('Copy', qtest=False),
    Key('Cut', qtest=False),
    Key('Display', qtest=False),  # Output switch key
    Key('DOS', qtest=False),
    Key('Documents', qtest=False),
    Key('Excel', 'Spreadsheet', qtest=False),
    Key('Explorer', 'Browser', qtest=False),
    Key('Game', qtest=False),
    Key('Go', qtest=False),
    Key('iTouch', qtest=False),
    Key('LogOff', 'Logoff', qtest=False),
    Key('Market', qtest=False),
    Key('Meeting', qtest=False),
    Key('MenuKB', 'Keyboard Menu', qtest=False),
    Key('MenuPB', 'Menu PB', qtest=False),
    Key('MySites', 'My Sites', qtest=False),
    Key('News', qtest=False),
    Key('OfficeHome', 'Home Office', qtest=False),
    Key('Option', qtest=False),
    Key('Paste', qtest=False),
    Key('Phone', qtest=False),
    Key('Calendar', qtest=False),
    Key('Reply', qtest=False),
    Key('Reload', qtest=False),
    Key('RotateWindows', 'Rotate Windows', qtest=False),
    Key('RotationPB', 'Rotation PB', qtest=False),
    Key('RotationKB', 'Rotation KB', qtest=False),
    Key('Save', qtest=False),
    Key('Send', qtest=False),
    Key('Spell', 'Spellchecker', qtest=False),
    Key('SplitScreen', 'Split Screen', qtest=False),
    Key('Support', qtest=False),
    Key('TaskPane', 'Task Panel', qtest=False),
    Key('Terminal', qtest=False),
    Key('Tools', qtest=False),
    Key('Travel', qtest=False),
    Key('Video', qtest=False),
    Key('Word', 'Word Processor', qtest=False),
    Key('Xfer', 'XFer', qtest=False),
    Key('ZoomIn', 'Zoom In', qtest=False),
    Key('ZoomOut', 'Zoom Out', qtest=False),
    Key('Away', qtest=False),
    Key('Messenger', qtest=False),
    Key('WebCam', qtest=False),
    Key('MailForward', 'Mail Forward', qtest=False),
    Key('Pictures', qtest=False),
    Key('Music', qtest=False),
    Key('Battery', qtest=False),
    Key('Bluetooth', qtest=False),
    Key('WLAN', 'Wireless', qtest=False),
    Key('UWB', 'Ultra Wide Band', qtest=False),
    Key('AudioForward', 'Media Fast Forward', qtest=False),
    Key('AudioRepeat', 'Audio Repeat', qtest=False),  # Toggle repeat mode
    Key('AudioRandomPlay', 'Audio Random Play', qtest=False),  # Toggle shuffle mode
    Key('Subtitle', qtest=False),
    Key('AudioCycleTrack', 'Audio Cycle Track', qtest=False),
    Key('Time', qtest=False),
    Key('Hibernate', qtest=False),
    Key('View', qtest=False),
    Key('TopMenu', 'Top Menu', qtest=False),
    Key('PowerDown', 'Power Down', qtest=False),
    Key('Suspend', qtest=False),
    Key('ContrastAdjust', 'Contrast Adjust', qtest=False),

    Key('LaunchG', 'Launch (G)', qtest=False),
    Key('LaunchH', 'Launch (H)', qtest=False),

    Key('TouchpadToggle', 'Touchpad Toggle', qtest=False),
    Key('TouchpadOn', 'Touchpad On', qtest=False),
    Key('TouchpadOff', 'Touchpad Off', qtest=False),

    Key('MicMute', 'Microphone Mute', qtest=False),

    Key('Red', qtest=False),
    Key('Green', qtest=False),
    Key('Yellow', qtest=False),
    Key('Blue', qtest=False),

    Key('ChannelUp', 'Channel Up', qtest=False),
    Key('ChannelDown', 'Channel Down', qtest=False),

    Key('Guide', qtest=False),
    Key('Info', qtest=False),
    Key('Settings', qtest=False),

    Key('MicVolumeUp', 'Microphone Volume Up', qtest=False),
    Key('MicVolumeDown', 'Microphone Volume Down', qtest=False),

    Key('New', qtest=False),
    Key('Open', qtest=False),
    Key('Find', qtest=False),
    Key('Undo', qtest=False),
    Key('Redo', qtest=False),

    Key('MediaLast', 'Media Last', qtest=False),

    ### Keypad navigation keys
    Key('Select', qtest=False),
    Key('Yes', qtest=False),
    Key('No', qtest=False),

    ### Newer misc keys
    Key('Cancel', qtest=False),
    Key('Printer', qtest=False),
    Key('Execute', qtest=False),
    Key('Sleep', qtest=False),
    Key('Play', qtest=False),  # Not the same as Key_MediaPlay
    Key('Zoom', qtest=False),
    # Key('Jisho', qtest=False),  # IME: Dictionary key
    # Key('Oyayubi_Left', qtest=False),  # IME: Left Oyayubi key
    # Key('Oyayubi_Right', qtest=False),  # IME: Right Oyayubi key
    Key('Exit', qtest=False),

    # Device keys
    Key('Context1', qtest=False),
    Key('Context2', qtest=False),
    Key('Context3', qtest=False),
    Key('Context4', qtest=False),
    Key('Call', qtest=False),  # set absolute state to in a call (do not toggle state)
    Key('Hangup', qtest=False),  # set absolute state to hang up (do not toggle state)
    Key('Flip', qtest=False),
    Key('ToggleCallHangup', 'Toggle Call/Hangup', qtest=False),  # a toggle key for answering, or hanging up, based on current call state
    Key('VoiceDial', 'Voice Dial', qtest=False),
    Key('LastNumberRedial', 'Last Number Redial', qtest=False),

    Key('Camera', 'Camera Shutter', qtest=False),
    Key('CameraFocus', 'Camera Focus', qtest=False),

    Key('unknown', 'Unknown', qtest=False),
    # 0x0 is used by Qt for unknown keys...
    Key(attribute='', name='nil', member=0x0, qtest=False),
]


MODIFIERS = [
    Modifier('Shift'),
    Modifier('Control', 'Ctrl'),
    Modifier('Alt'),
    Modifier('Meta'),
    Modifier('Keypad', 'Num'),
    Modifier('GroupSwitch', 'AltGr'),
]
