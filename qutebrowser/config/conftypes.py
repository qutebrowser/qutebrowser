# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Setting options used for qutebrowser."""

import re
import shlex
import os.path
from sre_constants import error as RegexError

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtNetwork import QNetworkProxy

import qutebrowser.commands.utils as cmdutils


class ValidationError(ValueError):

    """Exception raised when a value for a config type was invalid.

    Class attributes:
        section: Section in which the error occured (added when catching and
                 re-raising the exception).
        option: Option in which the error occured.
    """

    section = None
    option = None

    def __init__(self, value, msg):
        super().__init__("Invalid value '{}' - {}".format(value, msg))


class ValidValues:

    """Container for valid values for a given type.

    Attributes:
        values: A list with the allowed untransformed values.
        descriptions: A dict with value/desc mappings.
    """

    def __init__(self, *vals):
        self.descriptions = {}
        self.values = []
        for v in vals:
            if isinstance(v, str):
                # Value without description
                self.values.append(v)
            else:
                # (value, description) tuple
                self.values.append(v[0])
                self.descriptions[v[0]] = v[1]

    def __contains__(self, val):
        return val in self.values

    def __iter__(self):
        return self.values.__iter__()


class BaseType:

    """A type used for a setting value.

    Class attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. ValidValues instance.
        typestr: The name of the type to appear in the config.
    """

    typestr = None
    valid_values = None

    def transform(self, value):
        """Transform the setting value.

        This method can assume the value is indeed a valid value.

        The default implementation returns the original value.

        Args:
            value: The original string value.

        Return:
            The transformed value.
        """
        return value

    def validate(self, value):
        """Validate value against possible values.

        The default implementation checks the value against self.valid_values
        if it was defined.

        Args:
            value: The value to validate.

        Raise:
            ValidationError if the value was invalid.
            NotImplementedError if self.valid_values is not defined and this
                                method should be overridden.
        """
        if self.valid_values is not None:
            if value not in self.valid_values:
                raise ValidationError(value, "valid values: {}".format(
                    ','.join(self.valid_values)))
            else:
                return
        else:
            raise NotImplementedError("{} does not implement validate.".format(
                self.__class__.__name__))

    def complete(self):
        """Return a list of possible values for completion.

        The default implementation just returns valid_values, but it might be
        useful to override this for special cases.

        Return:
            A list of (value, description) tuples or None.
        """
        if self.valid_values is None:
            return None
        else:
            out = []
            for val in self.valid_values:
                try:
                    desc = self.valid_values.descriptions[val]
                except KeyError:
                    desc = ""
                out.append((val, desc))
            return out


class String(BaseType):

    """Base class for a string setting (case-insensitive).

    Attributes:
        minlen: Minimum length (inclusive).
        maxlen: Maximum length (inclusive).
        forbidden: Forbidden chars in the string.
        none: Whether to convert to None for an empty string.
    """

    typestr = 'string'

    def __init__(self, minlen=None, maxlen=None, forbidden=None, none=False):
        self.minlen = minlen
        self.maxlen = maxlen
        self.forbidden = forbidden
        self.none = none

    def transform(self, value):
        if self.none and not value:
            return None
        return value

    def validate(self, value):
        if self.forbidden is not None and any(c in value
                                              for c in self.forbidden):
            raise ValidationError(value, "may not contain the chars "
                                  "'{}'".format(self.forbidden))
        if self.minlen is not None and len(value) < self.minlen:
            raise ValidationError(value, "must be at least {} chars "
                                  "long!".format(self.minlen))
        if self.maxlen is not None and len(value) > self.maxlen:
            raise ValidationError(value, "must be at most {} long!".format(
                                  self.maxlen))


class List(BaseType):

    """Base class for a (string-)list setting."""

    typestr = 'string-list'

    def transform(self, value):
        return value.split(',')

    def validate(self, value):
        pass


class Bool(BaseType):

    """Base class for a boolean setting.

    Class attributes:
        _BOOLEAN_STATES: A dictionary of strings mapped to their bool meanings.
    """

    typestr = 'bool'

    # Taken from configparser
    _BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}

    def transform(self, value):
        return Bool._BOOLEAN_STATES[value.lower()]

    def validate(self, value):
        if value.lower() not in Bool._BOOLEAN_STATES:
            raise ValidationError(value, "must be a boolean!")

    def complete(self):
        return [('true', ''), ('false', '')]


class Int(BaseType):

    """Base class for an integer setting.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
        none: Whether to accept empty values as None.
    """

    typestr = 'int'

    def __init__(self, minval=None, maxval=None, none=False):
        self.minval = minval
        self.maxval = maxval
        self.none = none

    def transform(self, value):
        if self.none and not value:
            return None
        return int(value)

    def validate(self, value):
        if self.none and not value:
            return
        try:
            intval = int(value)
        except ValueError:
            raise ValidationError(value, "must be an integer!")
        if self.minval is not None and intval < self.minval:
            raise ValidationError(value, "must be {} or bigger!".format(
                                  self.minval))
        if self.maxval is not None and intval > self.maxval:
            raise ValidationError(value, "must be {} or smaller!".format(
                                  self.maxval))


class IntList(List):

    """Base class for an int-list setting."""

    typestr = 'int-list'

    def transform(self, value):
        vals = super().transform(value)
        return map(int, vals)

    def validate(self, value):
        try:
            self.transform(value)
        except ValueError:
            raise ValidationError(value, "must be a list of integers!")


class Float(BaseType):

    """Base class for an float setting.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    typestr = 'float'

    def __init__(self, minval=None, maxval=None):
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        return float(value)

    def validate(self, value):
        try:
            floatval = float(value)
        except ValueError:
            raise ValidationError(value, "must be a float!")
        if self.minval is not None and floatval < self.minval:
            raise ValidationError(value, "must be {} or bigger!".format(
                                  self.minval))
        if self.maxval is not None and floatval > self.maxval:
            raise ValidationError(value, "must be {} or smaller!".format(
                                  self.maxval))


class Perc(BaseType):

    """Percentage.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    typestr = 'percentage'

    def __init__(self, minval=None, maxval=None):
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        return int(value.rstrip('%'))

    def validate(self, value):
        if not value.endswith('%'):
            raise ValidationError(value, "does not end with %")
        try:
            intval = int(value.rstrip('%'))
        except ValueError:
            raise ValidationError(value, "invalid percentage!")
        if self.minval is not None and intval < self.minval:
            raise ValidationError(value, "must be {}% or more!".format(
                                  self.minval))
        if self.maxval is not None and intval > self.maxval:
            raise ValidationError(value, "must be {}% or less!".format(
                                  self.maxval))


class PercList(List):

    """Base class for a list of percentages.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    typestr = 'perc-list'

    def __init__(self, minval=None, maxval=None):
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        vals = super().transform(value)
        return [int(val.rstrip('%')) for val in vals]

    def validate(self, value):
        vals = super().transform(value)
        perctype = Perc(minval=self.minval, maxval=self.maxval)
        try:
            for val in vals:
                perctype.validate(val)
        except ValidationError:
            raise ValidationError(value, "must be a list of percentages!")


class PercOrInt(BaseType):

    """Percentage or integer.

    Attributes:
        minperc: Minimum value for percentage (inclusive).
        maxperc: Maximum value for percentage (inclusive).
        minint: Minimum value for integer (inclusive).
        maxint: Maximum value for integer (inclusive).
    """

    typestr = 'percentage-or-int'

    def __init__(self, minperc=None, maxperc=None, minint=None, maxint=None):
        self.minperc = minperc
        self.maxperc = maxperc
        self.minint = minint
        self.maxint = maxint

    def validate(self, value):
        if value.endswith('%'):
            try:
                intval = int(value.rstrip('%'))
            except ValueError:
                raise ValidationError(value, "invalid percentage!")
            if self.minperc is not None and intval < self.minperc:
                raise ValidationError(value, "must be {}% or more!".format(
                                      self.minperc))
            if self.maxperc is not None and intval > self.maxperc:
                raise ValidationError(value, "must be {}% or less!".format(
                                      self.maxperc))
        else:
            try:
                intval = int(value)
            except ValueError:
                raise ValidationError(value, "must be integer or percentage!")
        if self.minint is not None and intval < self.minint:
            raise ValidationError(value, "must be {} or bigger!".format(
                                  self.minint))
        if self.maxint is not None and intval > self.maxint:
            raise ValidationError(value, "must be {} or smaller!".format(
                                  self.maxint))


class Command(BaseType):

    """Base class for a command value with arguments."""

    typestr = 'command'

    def validate(self, value):
        if not value:
            return
        if value.split()[0] not in cmdutils.cmd_dict:
            raise ValidationError(value, "must be a valid command!")

    def complete(self):
        out = []
        for cmdname, obj in cmdutils.cmd_dict.items():
            out.append((cmdname, obj.desc))
        return out


class CssColor(BaseType):

    """Base class for a CSS color value."""

    typestr = 'css-color'

    def validate(self, value):
        if value.startswith('-'):
            # custom function name, won't validate.
            return
        if QColor.isValidColor(value):
            pass
        else:
            raise ValidationError(value, "must be a valid CSS color")


class Color(CssColor):

    """Base class for a color value.

    Class attributes:
        _GRADIENTS: Valid gradient function names.
    """

    typestr = 'color'

    _GRADIENTS = ('qlineargradient', 'qradialgradient', 'qconicalgradient')

    def validate(self, value):
        if any([value.startswith(start) for start in Color._GRADIENTS]):
            # We can't validate this further.
            return
        super().validate(value)


class Font(BaseType):

    """Base class for a font value."""

    typestr = 'font'

    def validate(self, value):
        # We can't really validate anything here
        pass


class Regex(BaseType):

    """A regular expression."""

    typestr = 'regex'

    def __init__(self, flags=0):
        self.flags = flags

    def validate(self, value):
        try:
            re.compile(value, self.flags)
        except RegexError as e:
            raise ValidationError(value, "must be a valid regex - " + str(e))

    def transform(self, value):
        return re.compile(value, self.flags)


class RegexList(List):

    """A list of regexes."""

    typestr = 'regex-list'

    def __init__(self, flags=0):
        self.flags = flags

    def transform(self, value):
        vals = super().transform(value)
        return [re.compile(pattern, self.flags) for pattern in vals]

    def validate(self, value):
        try:
            self.transform(value)
        except RegexError as e:
            raise ValidationError(value, "must be a list valid regexes - " +
                                  str(e))


class File(BaseType):

    """A file on the local filesystem."""

    typestr = 'file'

    def validate(self, value):
        if not os.path.isfile(value):
            raise ValidationError(value, "must be a valid file!")


class WebKitBytes(BaseType):

    """A size with an optional suffix.

    Attributes:
        maxsize: The maximum size to be used.

    Class attributes:
        SUFFIXES: A mapping of size suffixes to multiplicators.
    """

    SUFFIXES = {
        'k': 1024 ** 1,
        'm': 1024 ** 2,
        'g': 1024 ** 3,
        't': 1024 ** 4,
        'p': 1024 ** 5,
        'e': 1024 ** 6,
        'z': 1024 ** 7,
        'y': 1024 ** 8,
    }

    typestr = 'bytes'

    def __init__(self, maxsize=None):
        self.maxsize = maxsize

    def validate(self, value):
        if value == '':
            return
        try:
            val = self.transform(value)
        except ValueError:
            raise ValidationError(value, "must be a valid integer with "
                                         "optional suffix!")
        if self.maxsize is not None and val > self.maxsize:
            raise ValidationError(value, "must be {} "
                                         "maximum!".format(self.maxsize))
        if val < 0:
            raise ValidationError(value, "must be 0 minimum!")

    def transform(self, value):
        if value == '':
            return None
        if any(value.lower().endswith(c) for c in self.SUFFIXES):
            suffix = value[-1].lower()
            val = value[:-1]
            multiplicator = self.SUFFIXES[suffix]
        else:
            val = value
            multiplicator = 1
        return int(val) * multiplicator


class WebKitBytesList(List):

    """A size with an optional suffix.

    Attributes:
        length: The length of the list.
        bytestype: The webkit bytes type.
    """

    typestr = 'bytes-list'

    def __init__(self, maxsize=None, length=None):
        self.length = length
        self.bytestype = WebKitBytes(maxsize)

    def transform(self, value):
        if value == '':
            return None
        vals = super().transform(value)
        return [self.bytestype.transform(val) for val in vals]

    def validate(self, value):
        if value == '':
            return
        vals = super().transform(value)
        for val in vals:
            self.bytestype.validate(val)
        if any(val is None for val in vals):
            raise ValidationError(value, "all values need to be set!")
        if self.length is not None and len(vals) != self.length:
            raise ValidationError(value, "exactly {} values need to be "
                                         "set!".format(self.length))


class ShellCommand(String):

    """A shellcommand which is split via shlex.

    Attributes:
        placeholder: If there should be a placeholder.
    """

    typestr = 'shell-command'

    def __init__(self, placeholder=False):
        self.placeholder = placeholder
        super().__init__()

    def validate(self, value):
        super().validate(value)
        if self.placeholder and '{}' not in value:
            raise ValidationError(value, "needs to contain a {}-placeholder.")

    def transform(self, value):
        return shlex.split(value)


class ZoomPerc(Perc):

    """A percentage which needs to be in the current zoom percentages."""

    def validate(self, value):
        super().validate(value)
        # FIXME we should validate the percentage is in the list here.


class HintMode(BaseType):

    """Base class for the hints -> mode setting."""

    valid_values = ValidValues(('number', "Use numeric hints."),
                               ('letter', "Use the chars in hints -> chars."))


class Proxy(BaseType):

    """A proxy URL or special value."""

    valid_values = ValidValues(('system', "Use the system wide proxy."),
                               ('none', "Don't use any proxy"))

    PROXY_TYPES = {
        'http': QNetworkProxy.HttpProxy,
        'socks': QNetworkProxy.Socks5Proxy,
        'socks5': QNetworkProxy.Socks5Proxy,
    }

    def validate(self, value):
        if value in self.valid_values:
            return
        url = QUrl(value)
        if (url.isValid() and not url.isEmpty() and
                url.scheme() in self.PROXY_TYPES):
            if url.userName() and url.password():
                pass
            elif not url.userName() and not url.password():
                pass
            else:
                raise ValidationError(value, "must either have user and "
                                             "password or none of both")
        else:
            raise ValidationError(value, "must be a proxy URL (http://... or "
                                         "socks://...) or system/none!")

    def complete(self):
        out = []
        for val in self.valid_values:
            out.append((val, self.valid_values.descriptions[val]))
        out.append(('http://', 'HTTP proxy URL'))
        out.append(('socks://', 'SOCKS proxy URL'))
        return out

    def transform(self, value):
        if value == 'system':
            return None
        elif value == 'none':
            return QNetworkProxy(QNetworkProxy.NoProxy)
        url = QUrl(value)
        typ = self.PROXY_TYPES[url.scheme()]
        proxy = QNetworkProxy(typ, url.host())
        if url.port() != -1:
            proxy.setPort(url.port())
        if url.userName():
            proxy.setUser(url.userName())
        if url.password():
            proxy.setPassword(url.password())
        return proxy


class SearchEngineName(BaseType):

    """A search engine name."""

    def validate(self, value):
        pass


class SearchEngineUrl(BaseType):

    """A search engine URL."""

    def validate(self, value):
        if '{}' in value:
            pass
        else:
            raise ValidationError(value, "must contain \"{}\"")


class KeyBindingName(BaseType):

    """The name (keys) of a keybinding."""

    def validate(self, value):
        pass


class KeyBinding(Command):

    """The command of a keybinding."""

    pass


class WebSettingsFile(File):

    """QWebSettings file which also can be none."""

    typestr = 'file'

    def validate(self, value):
        if value == '':
            # empty values are okay
            return
        super().validate(value)

    def transform(self, value):
        if value == '':
            return None
        else:
            return QUrl.fromLocalFile(value)


class AutoSearch(BaseType):

    """Whether to start a search when something else than a URL is entered."""

    valid_values = ValidValues(('naive', "Use simple/naive check."),
                               ('dns', "Use DNS requests (might be slow!)."),
                               ('false', "Never search automatically."))

    def validate(self, value):
        if value.lower() in ('naive', 'dns'):
            pass
        else:
            Bool.validate(self, value)

    def transform(self, value):
        if value.lower() in ('naive', 'dns'):
            return value.lower()
        elif super().transform(value):
            # boolean true is an alias for naive matching
            return 'naive'
        else:
            return False


class Position(String):

    """The position of the tab bar."""

    valid_values = ValidValues('north', 'south', 'east', 'west')


class SelectOnRemove(String):

    """Which tab to select when the focused tab is removed."""

    valid_values = ValidValues(
        ('left', "Select the tab on the left."),
        ('right', "Select the tab on the right."),
        ('previous', "Select the previously selected tab."))


class LastClose(String):

    """Behaviour when the last tab is closed."""

    valid_values = ValidValues(('ignore', "Don't do anything."),
                               ('blank', "Load about:blank."),
                               ('quit', "Quit qutebrowser."))


class AcceptCookies(String):

    """Whether to accept a cookie."""

    valid_values = ValidValues(('default', "Default QtWebKit behaviour"),
                               ('never', "Don't accept cookies at all."))


class WindowOpenBehaviour(String):

    """What to do when a webview requests a new window."""

    valid_values = ValidValues(('same-tab', "Open new window in same tab."),
                               ('new-tab', "Open new window in new tab (note: "
                                           "history will be cleared)."))


class ConfirmQuit(String):

    """Whether to display a confirmation when the window is closed."""

    valid_values = ValidValues(('always', "Always show a confirmation."),
                               ('multiple-tabs', "Show a confirmation if "
                                                 "multiple tabs are opened."),
                               ('never', "Never show a confirmation."))
