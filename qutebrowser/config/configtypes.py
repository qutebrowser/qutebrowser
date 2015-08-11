# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import base64
import codecs
import os.path
import sre_constants
import itertools
import collections

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtNetwork import QNetworkProxy
from PyQt5.QtWidgets import QTabWidget, QTabBar

from qutebrowser.commands import cmdutils
from qutebrowser.config import configexc
from qutebrowser.utils import standarddir, utils


SYSTEM_PROXY = object()  # Return value for Proxy type

# Taken from configparser
BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                  '0': False, 'no': False, 'false': False, 'off': False}


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

    def __repr__(self):
        return utils.get_repr(self, values=self.values,
                              descriptions=self.descriptions)


class BaseType:

    """A type used for a setting value.

    Attributes:
        none_ok: Whether to convert to None for an empty string.

    Class attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. ValidValues instance.
        special: If set, the type is only used for one option and isn't
                 mentioned in the config file.
    """

    valid_values = None
    special = False

    def __init__(self, none_ok=False):
        self.none_ok = none_ok

    def _basic_validation(self, value):
        """Do some basic validation for the value (empty, non-printable chars).

        Arguments:
            value: The value to check.
        """
        if not value:
            if self.none_ok:
                return
            else:
                raise configexc.ValidationError(value, "may not be empty!")

        if any(ord(c) < 32 or ord(c) == 0x7f for c in value):
            raise configexc.ValidationError(value, "may not contain "
                                            "unprintable chars!")

    def transform(self, value):
        """Transform the setting value.

        This method can assume the value is indeed a valid value.

        The default implementation returns the original value.

        Args:
            value: The original string value.

        Return:
            The transformed value.
        """
        if not value:
            return None
        else:
            return value

    def validate(self, value):
        """Validate value against possible values.

        The default implementation checks the value against self.valid_values
        if it was defined.

        Args:
            value: The value to validate.
        """
        self._basic_validation(value)
        if not value:
            return
        if self.valid_values is not None:
            if value not in self.valid_values:
                raise configexc.ValidationError(
                    value, "valid values: {}".format(', '.join(
                        self.valid_values)))
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
                    # Some values are self-explaining and don't need a
                    # description.
                    desc = ""
                out.append((val, desc))
            return out


class MappingType(BaseType):

    """Base class for any setting which has a mapping to the given values.

    Attributes:
        MAPPING: The mapping to use.
    """

    MAPPING = {}

    def __init__(self, none_ok=False):
        super().__init__(none_ok)
        if list(sorted(self.MAPPING)) != list(sorted(self.valid_values)):
            raise ValueError("Mapping {!r} doesn't match valid values "
                             "{!r}".format(self.MAPPING, self.valid_values))

    def validate(self, value):
        super().validate(value.lower())

    def transform(self, value):
        if not value:
            return None
        return self.MAPPING[value.lower()]


class String(BaseType):

    """Base class for a string setting (case-insensitive).

    Attributes:
        minlen: Minimum length (inclusive).
        maxlen: Maximum length (inclusive).
        forbidden: Forbidden chars in the string.
    """

    def __init__(self, minlen=None, maxlen=None, forbidden=None,
                 none_ok=False):
        super().__init__(none_ok)
        if minlen is not None and minlen < 1:
            raise ValueError("minlen ({}) needs to be >= 1!".format(minlen))
        elif maxlen is not None and maxlen < 1:
            raise ValueError("maxlen ({}) needs to be >= 1!".format(maxlen))
        elif maxlen is not None and minlen is not None and maxlen < minlen:
            raise ValueError("minlen ({}) needs to be <= maxlen ({})!".format(
                minlen, maxlen))
        self.minlen = minlen
        self.maxlen = maxlen
        self.forbidden = forbidden

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        if self.forbidden is not None and any(c in value
                                              for c in self.forbidden):
            raise configexc.ValidationError(value, "may not contain the chars "
                                            "'{}'".format(self.forbidden))
        if self.minlen is not None and len(value) < self.minlen:
            raise configexc.ValidationError(value, "must be at least {} chars "
                                            "long!".format(self.minlen))
        if self.maxlen is not None and len(value) > self.maxlen:
            raise configexc.ValidationError(value, "must be at most {} chars "
                                            "long!".format(self.maxlen))


class List(BaseType):

    """Base class for a (string-)list setting."""

    def transform(self, value):
        if not value:
            return None
        else:
            return [v if v else None for v in value.split(',')]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        vals = self.transform(value)
        if None in vals:
            raise configexc.ValidationError(value, "items may not be empty!")


class Bool(BaseType):

    """Base class for a boolean setting."""

    valid_values = ValidValues('true', 'false')

    def transform(self, value):
        if not value:
            return None
        else:
            return BOOLEAN_STATES[value.lower()]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif value.lower() not in BOOLEAN_STATES:
            raise configexc.ValidationError(value, "must be a boolean!")


class BoolAsk(Bool):

    """A yes/no/ask question."""

    valid_values = ValidValues('true', 'false', 'ask')

    def transform(self, value):
        if value.lower() == 'ask':
            return 'ask'
        else:
            return super().transform(value)

    def validate(self, value):
        if value.lower() == 'ask':
            return
        else:
            super().validate(value)


class Int(BaseType):

    """Base class for an integer setting.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    def __init__(self, minval=None, maxval=None, none_ok=False):
        super().__init__(none_ok)
        if maxval is not None and minval is not None and maxval < minval:
            raise ValueError("minval ({}) needs to be <= maxval ({})!".format(
                minval, maxval))
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        if not value:
            return None
        else:
            return int(value)

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            intval = int(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be an integer!")
        if self.minval is not None and intval < self.minval:
            raise configexc.ValidationError(value, "must be {} or "
                                            "bigger!".format(self.minval))
        if self.maxval is not None and intval > self.maxval:
            raise configexc.ValidationError(value, "must be {} or "
                                            "smaller!".format(self.maxval))


class IntList(List):

    """Base class for an int-list setting."""

    def transform(self, value):
        if not value:
            return None
        vals = super().transform(value)
        return [int(v) if v is not None else None for v in vals]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            vals = self.transform(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be a list of "
                                            "integers!")
        if None in vals and not self.none_ok:
            raise configexc.ValidationError(value, "items may not be empty!")


class Float(BaseType):

    """Base class for an float setting.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    def __init__(self, minval=None, maxval=None, none_ok=False):
        super().__init__(none_ok)
        if maxval is not None and minval is not None and maxval < minval:
            raise ValueError("minval ({}) needs to be <= maxval ({})!".format(
                minval, maxval))
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        if not value:
            return None
        else:
            return float(value)

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            floatval = float(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be a float!")
        if self.minval is not None and floatval < self.minval:
            raise configexc.ValidationError(value, "must be {} or "
                                            "bigger!".format(self.minval))
        if self.maxval is not None and floatval > self.maxval:
            raise configexc.ValidationError(value, "must be {} or "
                                            "smaller!".format(self.maxval))


class Perc(BaseType):

    """Percentage.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    def __init__(self, minval=None, maxval=None, none_ok=False):
        super().__init__(none_ok)
        if maxval is not None and minval is not None and maxval < minval:
            raise ValueError("minval ({}) needs to be <= maxval ({})!".format(
                minval, maxval))
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        if not value:
            return
        else:
            return int(value[:-1])

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif not value.endswith('%'):
            raise configexc.ValidationError(value, "does not end with %")
        try:
            intval = int(value[:-1])
        except ValueError:
            raise configexc.ValidationError(value, "invalid percentage!")
        if self.minval is not None and intval < self.minval:
            raise configexc.ValidationError(value, "must be {}% or "
                                            "more!".format(self.minval))
        if self.maxval is not None and intval > self.maxval:
            raise configexc.ValidationError(value, "must be {}% or "
                                            "less!".format(self.maxval))


class PercList(List):

    """Base class for a list of percentages.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    def __init__(self, minval=None, maxval=None, none_ok=False):
        super().__init__(none_ok)
        if maxval is not None and minval is not None and maxval < minval:
            raise ValueError("minval ({}) needs to be <= maxval ({})!".format(
                minval, maxval))
        self.minval = minval
        self.maxval = maxval

    def transform(self, value):
        if not value:
            return None
        vals = super().transform(value)
        return [int(v[:-1]) if v is not None else None for v in vals]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        vals = super().transform(value)
        perctype = Perc(minval=self.minval, maxval=self.maxval)
        try:
            for val in vals:
                if val is None:
                    if self.none_ok:
                        continue
                    else:
                        raise configexc.ValidationError(value, "items may not "
                                                        "be empty!")
                else:
                    perctype.validate(val)
        except configexc.ValidationError:
            raise configexc.ValidationError(value, "must be a list of "
                                            "percentages!")


class PercOrInt(BaseType):

    """Percentage or integer.

    Attributes:
        minperc: Minimum value for percentage (inclusive).
        maxperc: Maximum value for percentage (inclusive).
        minint: Minimum value for integer (inclusive).
        maxint: Maximum value for integer (inclusive).
    """

    def __init__(self, minperc=None, maxperc=None, minint=None, maxint=None,
                 none_ok=False):
        super().__init__(none_ok)
        if maxint is not None and minint is not None and maxint < minint:
            raise ValueError("minint ({}) needs to be <= maxint ({})!".format(
                minint, maxint))
        if maxperc is not None and minperc is not None and maxperc < minperc:
            raise ValueError("minperc ({}) needs to be <= maxperc "
                             "({})!".format(minperc, maxperc))
        self.minperc = minperc
        self.maxperc = maxperc
        self.minint = minint
        self.maxint = maxint

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif value.endswith('%'):
            try:
                intval = int(value[:-1])
            except ValueError:
                raise configexc.ValidationError(value, "invalid percentage!")
            if self.minperc is not None and intval < self.minperc:
                raise configexc.ValidationError(value, "must be {}% or "
                                                "more!".format(self.minperc))
            if self.maxperc is not None and intval > self.maxperc:
                raise configexc.ValidationError(value, "must be {}% or "
                                                "less!".format(self.maxperc))
        else:
            try:
                intval = int(value)
            except ValueError:
                raise configexc.ValidationError(value, "must be integer or "
                                                "percentage!")
            if self.minint is not None and intval < self.minint:
                raise configexc.ValidationError(value, "must be {} or "
                                                "bigger!".format(self.minint))
            if self.maxint is not None and intval > self.maxint:
                raise configexc.ValidationError(value, "must be {} or "
                                                "smaller!".format(self.maxint))


class Command(BaseType):

    """Base class for a command value with arguments."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        splitted = value.split()
        if not splitted or splitted[0] not in cmdutils.cmd_dict:
            raise configexc.ValidationError(value, "must be a valid command!")

    def complete(self):
        out = []
        for cmdname, obj in cmdutils.cmd_dict.items():
            out.append((cmdname, obj.desc))
        return out


class ColorSystem(MappingType):

    """Color systems for interpolation."""

    special = True
    valid_values = ValidValues(('rgb', "Interpolate in the RGB color system."),
                               ('hsv', "Interpolate in the HSV color system."),
                               ('hsl', "Interpolate in the HSL color system."))

    MAPPING = {
        'rgb': QColor.Rgb,
        'hsv': QColor.Hsv,
        'hsl': QColor.Hsl,
    }


class QtColor(BaseType):

    """Base class for QColor."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif QColor.isValidColor(value):
            pass
        else:
            raise configexc.ValidationError(value, "must be a valid color")

    def transform(self, value):
        if not value:
            return None
        else:
            return QColor(value)


class CssColor(BaseType):

    """Base class for a CSS color value."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif value.startswith('-'):
            # custom function name, won't validate.
            pass
        elif QColor.isValidColor(value):
            pass
        else:
            raise configexc.ValidationError(value, "must be a valid color")


class QssColor(CssColor):

    """Base class for a color value.

    Class attributes:
        color_func_regexes: Valid function regexes.
    """

    color_func_regexes = [
        r'rgb\([0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?\)',
        r'rgba\([0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?\)',
        r'hsv\([0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?\)',
        r'hsva\([0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?, [0-9]{1,3}%?\)',
        r'qlineargradient\(.*\)',
        r'qradialgradient\(.*\)',
        r'qconicalgradient\(.*\)',
    ]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif any(re.match(r, value) for r in self.color_func_regexes):
            # QColor doesn't handle these, so we do the best we can easily
            pass
        elif QColor.isValidColor(value):
            pass
        else:
            raise configexc.ValidationError(value, "must be a valid color")


class Font(BaseType):

    """Base class for a font value."""

    font_regex = re.compile(r"""
        ^(
            (
                # style
                (?P<style>normal|italic|oblique) |
                # weight (named | 100..900)
                (
                    (?P<weight>[123456789]00) |
                    (?P<namedweight>normal|bold)
                ) |
                # size (<float>pt | <int>px)
                (?P<size>[0-9]+((\.[0-9]+)?[pP][tT]|[pP][xX]))
            )\                         # size/weight/style are space-separated
        )*                             # 0-inf size/weight/style tags
        (?P<family>[A-Za-z0-9, "-]*)$  # mandatory font family""", re.VERBOSE)

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif not self.font_regex.match(value):
            raise configexc.ValidationError(value, "must be a valid font")


class FontFamily(Font):

    """A Qt font family."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        match = self.font_regex.match(value)
        if not match:
            raise configexc.ValidationError(value, "must be a valid font")
        for group in 'style', 'weight', 'namedweight', 'size':
            if match.group(group):
                raise configexc.ValidationError(value, "may not include a "
                                                "{}!".format(group))


class QtFont(Font):

    """A Font which gets converted to a QFont."""

    def transform(self, value):
        if not value:
            return None
        style_map = {
            'normal': QFont.StyleNormal,
            'italic': QFont.StyleItalic,
            'oblique': QFont.StyleOblique,
        }
        weight_map = {
            'normal': QFont.Normal,
            'bold': QFont.Bold,
        }
        font = QFont()
        font.setStyle(QFont.StyleNormal)
        font.setWeight(QFont.Normal)

        match = self.font_regex.match(value)
        style = match.group('style')
        weight = match.group('weight')
        namedweight = match.group('namedweight')
        size = match.group('size')
        family = match.group('family')
        if style:
            font.setStyle(style_map[style])
        if namedweight:
            font.setWeight(weight_map[namedweight])
        if weight:
            # based on qcssparser.cpp:setFontWeightFromValue
            font.setWeight(min(int(weight) / 8, 99))
        if size:
            if size.lower().endswith('pt'):
                font.setPointSizeF(float(size[:-2]))
            elif size.lower().endswith('px'):
                font.setPixelSize(int(size[:-2]))
            else:
                # This should never happen as the regex only lets pt/px
                # through.
                raise ValueError("Unexpected size unit in {!r}!".format(
                    size))  # pragma: no cover
        # The Qt CSS parser handles " and ' before passing the string to
        # QFont.setFamily. We could do proper CSS-like parsing here, but since
        # hopefully nobody will ever have a font with quotes in the family (if
        # that's even possible), we take a much more naive approach.
        family = family.replace('"', '').replace("'", '')
        font.setFamily(family)
        return font


class Regex(BaseType):

    """A regular expression."""

    def __init__(self, flags=0, none_ok=False):
        super().__init__(none_ok)
        self.flags = flags

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            re.compile(value, self.flags)
        except sre_constants.error as e:
            raise configexc.ValidationError(value, "must be a valid regex - " +
                                            str(e))

    def transform(self, value):
        if not value:
            return None
        else:
            return re.compile(value, self.flags)


class RegexList(List):

    """A list of regexes."""

    def __init__(self, flags=0, none_ok=False):
        super().__init__(none_ok)
        self.flags = flags

    def transform(self, value):
        if not value:
            return None
        vals = super().transform(value)
        return [re.compile(v, self.flags) if v is not None else None
                for v in vals]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            vals = self.transform(value)
        except sre_constants.error as e:
            raise configexc.ValidationError(value, "must be a list valid "
                                            "regexes - " + str(e))
        if not self.none_ok and None in vals:
            raise configexc.ValidationError(value, "items may not be empty!")


class File(BaseType):

    """A file on the local filesystem."""

    def transform(self, value):
        if not value:
            return None
        value = os.path.expanduser(value)
        value = os.path.expandvars(value)
        if not os.path.isabs(value):
            cfgdir = standarddir.config()
            assert cfgdir is not None
            return os.path.join(cfgdir, value)
        return value

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        value = os.path.expanduser(value)
        value = os.path.expandvars(value)
        try:
            if not os.path.isabs(value):
                cfgdir = standarddir.config()
                if cfgdir is None:
                    raise configexc.ValidationError(
                        value, "must be an absolute path when not using a "
                        "config directory!")
                elif not os.path.isfile(os.path.join(cfgdir, value)):
                    raise configexc.ValidationError(
                        value, "must be a valid path relative to the config "
                        "directory!")
                else:
                    return
            elif not os.path.isfile(value):
                raise configexc.ValidationError(
                    value, "must be a valid file!")
        except UnicodeEncodeError as e:
            raise configexc.ValidationError(value, e)


class Directory(BaseType):

    """A directory on the local filesystem."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        value = os.path.expandvars(value)
        value = os.path.expanduser(value)
        try:
            if not os.path.isdir(value):
                raise configexc.ValidationError(
                    value, "must be a valid directory!")
            if not os.path.isabs(value):
                raise configexc.ValidationError(
                    value, "must be an absolute path!")
        except UnicodeEncodeError as e:
            raise configexc.ValidationError(value, e)

    def transform(self, value):
        if not value:
            return None
        value = os.path.expandvars(value)
        return os.path.expanduser(value)


class FormatString(BaseType):

    """A string with '{foo}'-placeholders."""

    def __init__(self, fields, none_ok=False):
        super().__init__(none_ok)
        self.fields = fields

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        s = self.transform(value)
        try:
            return s.format(**{k: '' for k in self.fields})
        except (KeyError, IndexError) as e:
            raise configexc.ValidationError(value, "Invalid placeholder "
                                            "{}".format(e))
        except ValueError as e:
            raise configexc.ValidationError(value, str(e))


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

    def __init__(self, maxsize=None, none_ok=False):
        super().__init__(none_ok)
        self.maxsize = maxsize

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            val = self.transform(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be a valid integer "
                                            "with optional suffix!")
        if self.maxsize is not None and val > self.maxsize:
            raise configexc.ValidationError(value, "must be {} "
                                            "maximum!".format(self.maxsize))
        if val < 0:
            raise configexc.ValidationError(value, "must be 0 minimum!")

    def transform(self, value):
        if not value:
            return None
        elif any(value.lower().endswith(c) for c in self.SUFFIXES):
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

    def __init__(self, maxsize=None, length=None, none_ok=False):
        super().__init__(none_ok)
        self.length = length
        self.bytestype = WebKitBytes(maxsize, none_ok=none_ok)

    def transform(self, value):
        if value == '':
            return None
        else:
            vals = super().transform(value)
            return [self.bytestype.transform(val) for val in vals]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        vals = super().transform(value)
        for val in vals:
            self.bytestype.validate(val)
        if self.length is not None and len(vals) != self.length:
            raise configexc.ValidationError(value, "exactly {} values need to "
                                            "be set!".format(self.length))


class ShellCommand(BaseType):

    """A shellcommand which is split via shlex.

    Attributes:
        placeholder: If there should be a placeholder.
    """

    def __init__(self, placeholder=False, none_ok=False):
        super().__init__(none_ok)
        self.placeholder = placeholder

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            shlex.split(value)
        except ValueError as e:
            raise configexc.ValidationError(value, str(e))
        if self.placeholder and '{}' not in self.transform(value):
            raise configexc.ValidationError(value, "needs to contain a "
                                            "{}-placeholder.")

    def transform(self, value):
        if not value:
            return None
        else:
            return shlex.split(value)


class HintMode(BaseType):

    """Base class for the hints -> mode setting."""

    special = True
    valid_values = ValidValues(('number', "Use numeric hints."),
                               ('letter', "Use the chars in the hints -> "
                                          "chars setting."))


class Proxy(BaseType):

    """A proxy URL or special value."""

    special = True
    valid_values = ValidValues(('system', "Use the system wide proxy."),
                               ('none', "Don't use any proxy"))

    PROXY_TYPES = {
        'http': QNetworkProxy.HttpProxy,
        'socks': QNetworkProxy.Socks5Proxy,
        'socks5': QNetworkProxy.Socks5Proxy,
    }

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif value in self.valid_values:
            return
        url = QUrl(value)
        if not url.isValid():
            raise configexc.ValidationError(value, "invalid url, {}".format(
                url.errorString()))
        elif url.scheme() not in self.PROXY_TYPES:
            raise configexc.ValidationError(value, "must be a proxy URL "
                                            "(http://... or socks://...) or "
                                            "system/none!")

    def complete(self):
        out = []
        for val in self.valid_values:
            out.append((val, self.valid_values.descriptions[val]))
        out.append(('http://', 'HTTP proxy URL'))
        out.append(('socks://', 'SOCKS proxy URL'))
        return out

    def transform(self, value):
        if not value:
            return None
        elif value == 'system':
            return SYSTEM_PROXY
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

    special = True

    def validate(self, value):
        self._basic_validation(value)


class SearchEngineUrl(BaseType):

    """A search engine URL."""

    special = True

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif '{}' not in value:
            raise configexc.ValidationError(value, "must contain \"{}\"")
        try:
            value.format("")
        except (KeyError, IndexError) as e:
            raise configexc.ValidationError(
                value, "may not contain {...} (use {{ and }} for literal {/})")
        except ValueError as e:
            raise configexc.ValidationError(value, str(e))

        url = QUrl(value.replace('{}', 'foobar'))
        if not url.isValid():
            raise configexc.ValidationError(value, "invalid url, {}".format(
                url.errorString()))


class FuzzyUrl(BaseType):

    """A single URL."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        from qutebrowser.utils import urlutils
        try:
            self.transform(value)
        except urlutils.InvalidUrlError as e:
            raise configexc.ValidationError(value, str(e))

    def transform(self, value):
        from qutebrowser.utils import urlutils
        if not value:
            return None
        else:
            return urlutils.fuzzy_url(value, do_search=False)


PaddingValues = collections.namedtuple('PaddingValues', ['top', 'bottom',
                                                         'left', 'right'])


class Padding(IntList):

    """Setting for paddings around elements."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            vals = self.transform(value)
        except (ValueError, TypeError):
            raise configexc.ValidationError(value, "must be a list of 4 "
                                            "integers!")
        if None in vals and not self.none_ok:
            raise configexc.ValidationError(value, "items may not be empty!")
        elems = self.transform(value)
        if any(e is not None and e < 0 for e in elems):
            raise configexc.ValidationError(value, "Values need to be "
                                            "positive!")

    def transform(self, value):
        elems = super().transform(value)
        if elems is None:
            return elems
        return PaddingValues(*elems)


class Encoding(BaseType):

    """Setting for a python encoding."""

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        try:
            codecs.lookup(value)
        except LookupError:
            raise configexc.ValidationError(value, "is not a valid encoding!")


class UserStyleSheet(File):

    """QWebSettings UserStyleSheet."""

    special = True

    def transform(self, value):
        if not value:
            return None
        path = super().transform(value)
        if os.path.exists(path):
            return QUrl.fromLocalFile(path)
        else:
            data = base64.b64encode(value.encode('utf-8')).decode('ascii')
            return QUrl("data:text/css;charset=utf-8;base64,{}".format(data))

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        value = os.path.expandvars(value)
        value = os.path.expanduser(value)
        try:
            super().validate(value)
        except configexc.ValidationError:
            try:
                if not os.path.isabs(value):
                    # probably a CSS, so we don't handle it as filename.
                    # FIXME We just try if it is encodable, maybe we should
                    # validate CSS?
                    # https://github.com/The-Compiler/qutebrowser/issues/115
                    value.encode('utf-8')
            except UnicodeEncodeError as e:
                raise configexc.ValidationError(value, str(e))


class AutoSearch(BaseType):

    """Whether to start a search when something else than a URL is entered."""

    special = True
    valid_values = ValidValues(('naive', "Use simple/naive check."),
                               ('dns', "Use DNS requests (might be slow!)."),
                               ('false', "Never search automatically."))

    def __init__(self, none_ok=False):
        super().__init__(none_ok)
        self.booltype = Bool(none_ok=none_ok)

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        elif value.lower() in ('naive', 'dns'):
            pass
        else:
            self.booltype.validate(value)

    def transform(self, value):
        if not value:
            return None
        elif value.lower() in ('naive', 'dns'):
            return value.lower()
        elif self.booltype.transform(value):
            # boolean true is an alias for naive matching
            return 'naive'
        else:
            return False


class Position(MappingType):

    """The position of the tab bar."""

    valid_values = ValidValues('top', 'bottom', 'left', 'right')

    MAPPING = {
        'top': QTabWidget.North,
        'bottom': QTabWidget.South,
        'left': QTabWidget.West,
        'right': QTabWidget.East,
    }


class VerticalPosition(BaseType):

    """The position of the download bar."""

    valid_values = ValidValues('top', 'bottom')


class UrlList(List):

    """A list of URLs."""

    def transform(self, value):
        if not value:
            return None
        else:
            return [QUrl.fromUserInput(v) if v else None
                    for v in value.split(',')]

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        vals = self.transform(value)
        for val in vals:
            if val is None:
                raise configexc.ValidationError(value, "values may not be "
                                                "empty!")
            elif not val.isValid():
                raise configexc.ValidationError(value, "invalid URL - "
                                                "{}".format(val.errorString()))


class SessionName(BaseType):

    """The name of a session."""

    special = True

    def validate(self, value):
        self._basic_validation(value)
        if value.startswith('_'):
            raise configexc.ValidationError(value, "may not start with '_'!")


class SelectOnRemove(MappingType):

    """Which tab to select when the focused tab is removed."""

    special = True
    valid_values = ValidValues(
        ('left', "Select the tab on the left."),
        ('right', "Select the tab on the right."),
        ('previous', "Select the previously selected tab."))

    MAPPING = {
        'left': QTabBar.SelectLeftTab,
        'right': QTabBar.SelectRightTab,
        'previous': QTabBar.SelectPreviousTab,
    }


class LastClose(BaseType):

    """Behavior when the last tab is closed."""

    special = True
    valid_values = ValidValues(('ignore', "Don't do anything."),
                               ('blank', "Load a blank page."),
                               ('startpage', "Load the start page."),
                               ('default-page', "Load the default page."),
                               ('close', "Close the window."))


class AcceptCookies(BaseType):

    """Control which cookies to accept."""

    special = True
    valid_values = ValidValues(('all', "Accept all cookies."),
                               ('no-3rdparty', "Accept cookies from the same"
                                " origin only."),
                               ('no-unknown-3rdparty', "Accept cookies from "
                                "the same origin only, unless a cookie is "
                                "already set for the domain."),
                               ('never', "Don't accept cookies at all."))


class ConfirmQuit(List):

    """Whether to display a confirmation when the window is closed."""

    special = True
    valid_values = ValidValues(('always', "Always show a confirmation."),
                               ('multiple-tabs', "Show a confirmation if "
                                                 "multiple tabs are opened."),
                               ('downloads', "Show a confirmation if "
                                             "downloads are running"),
                               ('never', "Never show a confirmation."))
    # Values that can be combined with commas
    combinable_values = ('multiple-tabs', 'downloads')

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        values = []
        for v in self.transform(value):
            if v:
                values.append(v)
            elif self.none_ok:
                pass
            else:
                raise configexc.ValidationError(value, "May not contain empty "
                                                       "values!")
        # Never can't be set with other options
        if 'never' in values and len(values) > 1:
            raise configexc.ValidationError(
                value, "List cannot contain never!")
        # Always can't be set with other options
        elif 'always' in values and len(values) > 1:
            raise configexc.ValidationError(
                value, "List cannot contain always!")
        # Values have to be valid
        elif not set(values).issubset(set(self.valid_values.values)):
            raise configexc.ValidationError(
                value, "List contains invalid values!")
        # List can't have duplicates
        elif len(set(values)) != len(values):
            raise configexc.ValidationError(
                value, "List contains duplicate values!")

    def complete(self):
        combinations = []
        # Generate combinations of the options that can be combined
        for size in range(2, len(self.combinable_values) + 1):
            combinations += list(
                itertools.combinations(self.combinable_values, size))
        out = []
        # Add valid single values
        for val in self.valid_values:
            out.append((val, self.valid_values.descriptions[val]))
        # Add combinations to list of options
        for val in combinations:
            desc = ''
            out.append((','.join(val), desc))
        return out


class ForwardUnboundKeys(BaseType):

    """Whether to forward unbound keys."""

    special = True
    valid_values = ValidValues(('all', "Forward all unbound keys."),
                               ('auto', "Forward unbound non-alphanumeric "
                                        "keys."),
                               ('none', "Don't forward any keys."))


class CloseButton(BaseType):

    """Mouse button used to close tabs."""

    special = True
    valid_values = ValidValues(('right', "Close tabs on right-click."),
                               ('middle', "Close tabs on middle-click."),
                               ('none', "Don't close tabs using the mouse."))


class NewTabPosition(BaseType):

    """How new tabs are positioned."""

    special = True
    valid_values = ValidValues(('left', "On the left of the current tab."),
                               ('right', "On the right of the current tab."),
                               ('first', "At the left end."),
                               ('last', "At the right end."))


class IgnoreCase(Bool):

    """Whether to ignore case when searching."""

    special = True
    valid_values = ValidValues(('true', "Search case-insensitively"),
                               ('false', "Search case-sensitively"),
                               ('smart', "Search case-sensitively if there "
                                         "are capital chars"))

    def transform(self, value):
        if value.lower() == 'smart':
            return 'smart'
        else:
            return super().transform(value)

    def validate(self, value):
        self._basic_validation(value)
        if not value:
            return
        if value.lower() == 'smart':
            return
        else:
            super().validate(value)


class NewInstanceOpenTarget(BaseType):

    """How to open links in an existing instance if a new one is launched."""

    special = True
    valid_values = ValidValues(('tab', "Open a new tab in the existing "
                                       "window and activate the window."),
                               ('tab-bg', "Open a new background tab in the "
                                          "existing window and activate the "
                                          "window."),
                               ('tab-silent', "Open a new tab in the existing "
                                              "window without activating "
                                              "the window."),
                               ('tab-bg-silent', "Open a new background tab "
                                                 "in the existing window "
                                                 "without activating the "
                                                 "window."),
                               ('window', "Open in a new window."))


class DownloadPathSuggestion(BaseType):

    """How to format the question when downloading."""

    special = True
    valid_values = ValidValues(('path', "Show only the download path."),
                               ('filename', "Show only download filename."),
                               ('both', "Show download path and filename."))


class Referer(BaseType):

    """Send the Referer header."""

    valid_values = ValidValues(('always', "Always send."),
                               ('never', "Never send; this is not recommended,"
                                   " as some sites may break."),
                               ('same-domain', "Only send for the same domain."
                                   " This will still protect your privacy, but"
                                   " shouldn't break any sites."))


class UserAgent(BaseType):

    """The user agent to use."""

    special = True

    def __init__(self, none_ok=False):
        super().__init__(none_ok)

    def validate(self, value):
        self._basic_validation(value)

    def complete(self):
        """Complete a list of common user agents."""
        out = [
            ('Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20100101 '
             'Firefox/35.0',
             "Firefox 35.0 Win7 64-bit"),
            ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:35.0) Gecko/20100101 '
             'Firefox/35.0',
             "Firefox 35.0 Ubuntu"),
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:35.0) '
             'Gecko/20100101 Firefox/35.0',
             "Firefox 35.0 MacOSX"),

            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) '
             'AppleWebKit/600.3.18 (KHTML, like Gecko) Version/8.0.3 '
             'Safari/600.3.18',
             "Safari 8.0 MacOSX"),

            ('Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, '
             'like Gecko) Chrome/40.0.2214.111 Safari/537.36',
             "Chrome 40.0 Win7 64-bit"),
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) '
             'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.111 '
             'Safari/537.36',
             "Chrome 40.0 MacOSX"),
            ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/40.0.2214.111 Safari/537.36',
             "Chrome 40.0 Linux"),

            ('Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like '
             'Gecko',
             "IE 11.0 Win7 64-bit"),

            ('Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_2 like Mac OS X) '
             'AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 '
             'Mobile/12B440 Safari/600.1.4',
             "Mobile Safari 8.0 iOS"),
            ('Mozilla/5.0 (Android; Mobile; rv:35.0) Gecko/35.0 Firefox/35.0',
             "Firefox 35, Android"),
            ('Mozilla/5.0 (Linux; Android 5.0.2; One Build/KTU84L.H4) '
             'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
             'Chrome/37.0.0.0 Mobile Safari/537.36',
             "Android Browser"),

            ('Mozilla/5.0 (compatible; Googlebot/2.1; '
             '+http://www.google.com/bot.html',
             "Google Bot"),
            ('Wget/1.16.1 (linux-gnu)',
             "wget 1.16.1"),
            ('curl/7.40.0',
             "curl 7.40.0")
        ]
        return out


class TabBarShow(BaseType):

    """When to show the tab bar."""

    valid_values = ValidValues(('always', "Always show the tab bar."),
                               ('never', "Always hide the tab bar."),
                               ('multiple', "Hide the tab bar if only one tab "
                                            "is open."),
                               ('switching', "Show the tab bar when switching "
                                             "tabs."))
