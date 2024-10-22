# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Types for options in qutebrowser's configuration.

Those types are used in configdata.yml as type of a setting.

Most of them are pretty generic, but some of them are e.g. specific String
subclasses with valid_values set, as that particular "type" is used multiple
times in the config.

A setting value can be represented in three different ways:

1) As an object which can be represented in YAML:
   str, list, dict, int, float, True/False/None
   This is what qutebrowser actually saves internally, and also what it gets
   from the YAML or config.py.
2) As a string. This is e.g. used by the :set command.
3) As the value the code which uses it expects, e.g. enum members.

Config types can do different conversations:

- Object to string with .to_str() (1 -> 2)
- String to object with .from_str() (2 -> 1)
- Object to code with .to_py() (1 -> 3)
  This also validates whether the object is actually correct (type/value).
"""

import re
import html
import codecs
import os.path
import itertools
import functools
import operator
import json
import dataclasses
from typing import Any, Optional, Union
from re import Pattern
from collections.abc import Iterable, Iterator, Sequence, Callable

import yaml
from qutebrowser.qt.core import QUrl, Qt
from qutebrowser.qt.gui import QColor
from qutebrowser.qt.widgets import QTabWidget, QTabBar
from qutebrowser.qt.network import QNetworkProxy

from qutebrowser.misc import objects, debugcachestats
from qutebrowser.config import configexc, configutils
from qutebrowser.utils import (standarddir, utils, qtutils, urlutils, urlmatch,
                               usertypes, log)
from qutebrowser.keyinput import keyutils
from qutebrowser.browser.network import pac


class _SystemProxy:

    pass


SYSTEM_PROXY = _SystemProxy()  # Return value for Proxy type

# Taken from configparser
BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                  '0': False, 'no': False, 'false': False, 'off': False}


_Completions = Optional[Iterable[tuple[str, str]]]
_StrUnset = Union[str, usertypes.Unset]
_UnsetNone = Union[None, usertypes.Unset]
_StrUnsetNone = Union[str, _UnsetNone]


def _validate_encoding(encoding: Optional[str], value: str) -> None:
    """Check if the given value fits into the given encoding.

    Raises ValidationError if not.
    """
    if encoding is None:
        return

    try:
        value.encode(encoding)
    except UnicodeEncodeError as e:
        msg = f"{value!r} contains non-{encoding} characters: {e}"
        raise configexc.ValidationError(value, msg)


class ValidValues:

    """Container for valid values for a given type.

    Attributes:
        values: A list with the allowed untransformed values.
        descriptions: A dict with value/desc mappings.
        generate_docs: Whether to show the values in the docs.
        others_permitted: Whether arbitrary values are permitted.
                          Used to show buttons in qute://settings.
    """

    def __init__(
            self,
            *values: Union[
                str,
                dict[str, Optional[str]],
                tuple[str, Optional[str]],
            ],
            generate_docs: bool = True,
            others_permitted: bool = False
    ) -> None:
        if not values:
            raise ValueError("ValidValues with no values makes no sense!")
        self.descriptions: dict[str, str] = {}
        self.values: list[str] = []
        self.generate_docs = generate_docs
        self.others_permitted = others_permitted
        for value in values:
            if isinstance(value, str):
                # Value without description
                val = value
                desc = None
            elif isinstance(value, dict):
                # List of dicts from configdata.yml
                assert len(value) == 1, value
                val, desc = list(value.items())[0]
            else:
                val, desc = value

            self.values.append(val)
            if desc is not None:
                self.descriptions[val] = desc

    def __contains__(self, val: str) -> bool:
        return val in self.values

    def __iter__(self) -> Iterator[str]:
        return self.values.__iter__()

    def __repr__(self) -> str:
        return utils.get_repr(self, values=self.values,
                              descriptions=self.descriptions)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, ValidValues)
        return (self.values == other.values and
                self.descriptions == other.descriptions)


class BaseType:

    """A type used for a setting value.

    Attributes:
        none_ok: Whether to allow None (or an empty string for :set) as value.
        _completions: Override for completions for the given setting.

    Class attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. ValidValues instance.
    """

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        self._completions = completions
        self.none_ok = none_ok
        self.valid_values: Optional[ValidValues] = None

    def get_name(self) -> str:
        """Get a name for the type for documentation."""
        return self.__class__.__name__

    def get_valid_values(self) -> Optional[ValidValues]:
        """Get the type's valid values for documentation."""
        return self.valid_values

    def _basic_py_validation(
            self, value: Any,
            pytype: Union[type, tuple[type, ...]]) -> None:
        """Do some basic validation for Python values (emptyness, type).

        Arguments:
            value: The value to check.
            pytype: A Python type to check the value against.
        """
        if isinstance(value, usertypes.Unset):
            return

        if (value is None or (pytype == list and value == []) or
                (pytype == dict and value == {})):
            if not self.none_ok:
                raise configexc.ValidationError(value, "may not be null!")
            return

        if (not isinstance(value, pytype) or
                pytype is int and isinstance(value, bool)):
            if isinstance(pytype, tuple):
                expected = ' or '.join(typ.__name__ for typ in pytype)
            else:
                expected = pytype.__name__
            raise configexc.ValidationError(
                value, "expected a value of type {} but got {}.".format(
                    expected, type(value).__name__))

        if isinstance(value, str):
            self._basic_str_validation(value)

    def _basic_str_validation(self, value: str) -> None:
        """Do some basic validation for string values.

        This checks that the value isn't empty and doesn't contain any
        unprintable chars.

        Arguments:
            value: The value to check.
        """
        assert isinstance(value, str), value
        if not value and not self.none_ok:
            raise configexc.ValidationError(value, "may not be empty!")
        BaseType._basic_str_validation_cache(value)

    @staticmethod
    @debugcachestats.register(name='str validation cache')
    @functools.lru_cache(maxsize=2**9)
    def _basic_str_validation_cache(value: str) -> None:
        """Cache validation result to prevent looping over strings."""
        if any(ord(c) < 32 or ord(c) == 0x7f for c in value):
            raise configexc.ValidationError(
                value, "may not contain unprintable chars!")

    def _validate_surrogate_escapes(self, full_value: Any, value: Any) -> None:
        """Make sure the given value doesn't contain surrogate escapes.

        This is used for values passed to json.dump, as it can't handle those.
        """
        if not isinstance(value, str):
            return
        if any(ord(c) > 0xFFFF for c in value):
            raise configexc.ValidationError(
                full_value, "may not contain surrogate escapes!")

    def _validate_valid_values(self, value: str) -> None:
        """Validate value against possible values.

        The default implementation checks the value against self.valid_values
        if it was defined.

        Args:
            value: The value to validate.
        """
        if self.valid_values is not None:
            if value not in self.valid_values:
                raise configexc.ValidationError(
                    value,
                    "valid values: {}".format(', '.join(self.valid_values)))

    def from_str(self, value: str) -> Any:
        """Get the setting value from a string.

        By default this invokes to_py() for validation and returns the
        unaltered value. This means that if to_py() returns a string rather
        than something more sophisticated, this doesn't need to be implemented.

        Args:
            value: The original string value.

        Return:
            The transformed value.
        """
        self._basic_str_validation(value)
        self.to_py(value)  # for validation
        if not value:
            return None
        return value

    def from_obj(self, value: Any) -> Any:
        """Get the setting value from a config.py/YAML object."""
        return value

    def to_py(self, value: Any) -> Any:
        """Get the setting value from a Python value.

        Args:
            value: The value we got from Python/YAML.

        Return:
            The transformed value.

        Raise:
            configexc.ValidationError if the value was invalid.
        """
        raise NotImplementedError

    def to_str(self, value: Any) -> str:
        """Get a string from the setting value.

        The resulting string should be parseable again by from_str.
        """
        if value is None:
            return ''
        assert isinstance(value, str), value
        return value

    def to_doc(self, value: Any, indent: int = 0) -> str:
        """Get a string with the given value for the documentation.

        This currently uses asciidoc syntax.
        """
        utils.unused(indent)  # only needed for Dict/List
        str_value = self.to_str(value)
        if not str_value:
            return 'empty'
        return '+pass:[{}]+'.format(html.escape(str_value).replace(']', '\\]'))

    def complete(self) -> _Completions:
        """Return a list of possible values for completion.

        The default implementation just returns valid_values, but it might be
        useful to override this for special cases.

        Return:
            A list of (value, description) tuples or None.
        """
        if self._completions is not None:
            return self._completions
        elif self.valid_values is None:
            return None
        return [
            (val, self.valid_values.descriptions.get(val, ""))
            for val in self.valid_values
        ]

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, completions=self._completions)


class MappingType(BaseType):

    """Base class for any setting which has a mapping to the given values.

    Attributes:
        MAPPING: A mapping from config values to (translated_value, docs) tuples.
    """

    MAPPING: dict[str, tuple[Any, Optional[str]]] = {}

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues(
            *[(key, doc) for (key, (_val, doc)) in self.MAPPING.items()])

    def to_py(self, value: Any) -> Any:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None
        self._validate_valid_values(value.lower())
        mapped, _doc = self.MAPPING[value.lower()]
        return mapped

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok,
                              valid_values=self.valid_values)


class String(BaseType):

    """A string value.

    See the setting's valid values for more information on allowed values.

    Attributes:
        minlen: Minimum length (inclusive).
        maxlen: Maximum length (inclusive).
        forbidden: Forbidden chars in the string.
        regex: A regex used to validate the string.
        encoding: The encoding the value needs to fit in.
        completions: completions to be used, or None
    """

    def __init__(
            self, *,
            minlen: int = None,
            maxlen: int = None,
            forbidden: str = None,
            regex: str = None,
            encoding: str = None,
            none_ok: bool = False,
            completions: _Completions = None,
            valid_values: ValidValues = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = valid_values

        if minlen is not None and minlen < 1:
            raise ValueError("minlen ({}) needs to be >= 1!".format(minlen))
        if maxlen is not None and maxlen < 1:
            raise ValueError("maxlen ({}) needs to be >= 1!".format(maxlen))
        if maxlen is not None and minlen is not None and maxlen < minlen:
            raise ValueError("minlen ({}) needs to be <= maxlen ({})!".format(
                minlen, maxlen))
        self.minlen = minlen
        self.maxlen = maxlen
        self.forbidden = forbidden
        self.encoding = encoding
        self.regex = regex

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        _validate_encoding(self.encoding, value)
        self._validate_valid_values(value)

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
        if self.regex is not None and not re.fullmatch(self.regex, value):
            raise configexc.ValidationError(value, "does not match {}"
                                            .format(self.regex))

        return value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok,
                              valid_values=self.valid_values,
                              minlen=self.minlen,
                              maxlen=self.maxlen, forbidden=self.forbidden,
                              regex=self.regex, completions=self._completions,
                              encoding=self.encoding)


class UniqueCharString(String):

    """A string which may not contain duplicate chars."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        py_value = super().to_py(value)
        if isinstance(py_value, usertypes.Unset):
            return py_value
        elif not py_value:
            return None

        # Check for duplicate values
        if len(set(py_value)) != len(py_value):
            raise configexc.ValidationError(
                py_value, "String contains duplicate values!")

        return py_value


class List(BaseType):

    """A list of values.

    When setting from a string, pass a json-like list, e.g. `["one", "two"]`.
    """

    _show_valtype = True

    def __init__(
            self,
            valtype: BaseType,
            *,
            length: int = None,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valtype = valtype
        self.length = length

    def get_name(self) -> str:
        name = super().get_name()
        if self._show_valtype:
            name += " of " + self.valtype.get_name()
        return name

    def get_valid_values(self) -> Optional[ValidValues]:
        return self.valtype.get_valid_values()

    def from_str(self, value: str) -> Optional[list]:
        self._basic_str_validation(value)
        if not value:
            return None

        try:
            yaml_val = utils.yaml_load(value)
        except yaml.YAMLError as e:
            raise configexc.ValidationError(value, str(e))

        # For the values, we actually want to call to_py, as we did parse them
        # from YAML, so they are numbers/booleans/... already.
        self.to_py(yaml_val)
        return yaml_val

    def from_obj(self, value: Optional[list]) -> list:
        if value is None:
            return []
        return [self.valtype.from_obj(v) for v in value]

    def to_py(
            self,
            value: Union[list, usertypes.Unset]
    ) -> Union[list, usertypes.Unset]:
        self._basic_py_validation(value, list)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return []

        for val in value:
            self._validate_surrogate_escapes(value, val)

        if self.length is not None and len(value) != self.length:
            raise configexc.ValidationError(value, "Exactly {} values need to "
                                            "be set!".format(self.length))
        return [self.valtype.to_py(v) for v in value]

    def to_str(self, value: list) -> str:
        if not value:
            # An empty list is treated just like None -> empty string
            return ''
        return json.dumps(value)

    def to_doc(self, value: list, indent: int = 0) -> str:
        if not value:
            return 'empty'

        # Might work, but untested
        assert not isinstance(self.valtype, (Dict, List)), self.valtype

        lines = ['\n']
        prefix = '-' if not indent else '*' * indent
        for elem in value:
            lines.append('{} {}'.format(
                prefix,
                self.valtype.to_doc(elem, indent=indent+1)))
        return '\n'.join(lines)

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, valtype=self.valtype,
                              length=self.length)


class ListOrValue(BaseType):

    """A list of values, or a single value.

    //

    Internally, the value is stored as either a value (of valtype), or a list.
    to_py() then ensures that it's always a list.
    """

    _show_valtype = True

    def __init__(
            self,
            valtype: BaseType,
            *,
            none_ok: bool = False,
            completions: _Completions = None,
            **kwargs: Any,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        assert not isinstance(valtype, (List, ListOrValue)), valtype
        self.listtype = List(valtype=valtype, none_ok=none_ok, **kwargs)
        self.valtype = valtype

    def _val_and_type(self, value: Any) -> tuple[Any, BaseType]:
        """Get the value and type to use for to_str/to_doc/from_str."""
        if isinstance(value, list):
            if len(value) == 1:
                return value[0], self.valtype
            else:
                return value, self.listtype
        else:
            return value, self.valtype

    def get_name(self) -> str:
        return self.listtype.get_name() + ', or ' + self.valtype.get_name()

    def get_valid_values(self) -> Optional[ValidValues]:
        return self.valtype.get_valid_values()

    def from_str(self, value: str) -> Any:
        try:
            return self.listtype.from_str(value)
        except configexc.ValidationError:
            return self.valtype.from_str(value)

    def from_obj(self, value: Any) -> Any:
        if value is None:
            return []
        return value

    def to_py(self, value: Any) -> Any:
        if isinstance(value, usertypes.Unset):
            return value

        try:
            return [self.valtype.to_py(value)]
        except configexc.ValidationError:
            return self.listtype.to_py(value)

    def to_str(self, value: Any) -> str:
        if value is None:
            return ''

        val, typ = self._val_and_type(value)
        return typ.to_str(val)

    def to_doc(self, value: Any, indent: int = 0) -> str:
        if value is None:
            return 'empty'

        val, typ = self._val_and_type(value)
        return typ.to_doc(val)

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, valtype=self.valtype)


class FlagList(List):

    """A list of flags.

    Lists with duplicate flags are invalid. Each item is checked against
    the valid values of the setting.
    """

    combinable_values: Optional[Sequence] = None

    _show_valtype = False

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
            valid_values: ValidValues = None,
            length: int = None,
    ) -> None:
        super().__init__(
            valtype=String(),
            none_ok=none_ok,
            length=length,
            completions=completions,
        )
        self.valtype.valid_values = valid_values

    def _check_duplicates(self, values: list) -> None:
        if len(set(values)) != len(values):
            raise configexc.ValidationError(
                values, "List contains duplicate values!")

    def to_py(
            self,
            value: Union[usertypes.Unset, list],
    ) -> Union[usertypes.Unset, list]:
        vals = super().to_py(value)
        if not isinstance(vals, usertypes.Unset):
            self._check_duplicates(vals)
        return vals

    def complete(self) -> _Completions:
        if self._completions is not None:
            return self._completions

        valid_values = self.valtype.valid_values
        if valid_values is None:
            return None

        out = []
        # Single value completions
        for value in valid_values:
            desc = valid_values.descriptions.get(value, "")
            out.append((json.dumps([value]), desc))

        combinables = self.combinable_values
        if combinables is None:
            combinables = list(valid_values)
        # Generate combinations of each possible value combination
        for size in range(2, len(combinables) + 1):
            for combination in itertools.combinations(combinables, size):
                out.append((json.dumps(combination), ''))
        return out

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok,
                              valid_values=self.valid_values,
                              length=self.length)


class Bool(BaseType):

    """A boolean setting, either `true` or `false`.

    When setting from a string, `1`, `yes`, `on` and `true` count as true,
    while `0`, `no`, `off` and `false` count as false (case-insensitive).
    """

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues('true', 'false', generate_docs=False)

    def to_py(self, value: Union[bool, str, None]) -> Optional[bool]:
        self._basic_py_validation(value, bool)
        assert not isinstance(value, str)
        return value

    def from_str(self, value: str) -> Optional[bool]:
        self._basic_str_validation(value)
        if not value:
            return None

        try:
            return BOOLEAN_STATES[value.lower()]
        except KeyError:
            raise configexc.ValidationError(value, "must be a boolean!")

    def to_str(self, value: Optional[bool]) -> str:
        mapping = {
            None: '',
            True: 'true',
            False: 'false',
        }
        return mapping[value]


class BoolAsk(Bool):

    """Like `Bool`, but `ask` is allowed as additional value."""

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues('true', 'false', 'ask')

    def to_py(self,  # type: ignore[override]
              value: Union[bool, str]) -> Union[bool, str, None]:
        # basic validation unneeded if it's == 'ask' and done by Bool if we
        # call super().to_py
        if isinstance(value, str) and value.lower() == 'ask':
            return 'ask'
        return super().to_py(value)

    def from_str(self,  # type: ignore[override]
                 value: str) -> Union[bool, str, None]:
        # basic validation unneeded if it's == 'ask' and done by Bool if we
        # call super().from_str
        if value.lower() == 'ask':
            return 'ask'
        return super().from_str(value)

    def to_str(self, value: Union[bool, str, None]) -> str:
        mapping = {
            None: '',
            True: 'true',
            False: 'false',
            'ask': 'ask',
        }
        return mapping[value]


class _Numeric(BaseType):  # pylint: disable=abstract-method

    """Base class for Float/Int.

    Attributes:
        minval: Minimum value (inclusive).
        maxval: Maximum value (inclusive).
    """

    def __init__(
            self, *,
            minval: int = None,
            maxval: int = None,
            zero_ok: bool = True,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.minval = self._parse_bound(minval)
        self.maxval = self._parse_bound(maxval)
        self.zero_ok = zero_ok
        if self.maxval is not None and self.minval is not None:
            if self.maxval < self.minval:
                raise ValueError("minval ({}) needs to be <= maxval ({})!"
                                 .format(self.minval, self.maxval))

    def _parse_bound(
            self, bound: Union[None, str, int, float]
    ) -> Union[None, int, float]:
        """Get a numeric bound from a string like 'maxint'."""
        if bound == 'maxint':
            return qtutils.MAXVALS['int']
        elif bound == 'maxint64':
            return qtutils.MAXVALS['int64']
        else:
            if bound is not None:
                assert isinstance(bound, (int, float)), bound
            return bound

    def _validate_bounds(self,
                         value: Union[int, float, _UnsetNone],
                         suffix: str = '') -> None:
        """Validate self.minval and self.maxval."""
        if value is None:
            return
        elif isinstance(value, usertypes.Unset):
            return
        elif self.minval is not None and value < self.minval:
            raise configexc.ValidationError(
                value, "must be {}{} or bigger!".format(self.minval, suffix))
        elif self.maxval is not None and value > self.maxval:
            raise configexc.ValidationError(
                value, "must be {}{} or smaller!".format(self.maxval, suffix))
        elif not self.zero_ok and value == 0:
            raise configexc.ValidationError(value, "must not be 0!")

    def to_str(self, value: Union[None, int, float]) -> str:
        if value is None:
            return ''
        return str(value)

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, minval=self.minval,
                              maxval=self.maxval)


class Int(_Numeric):

    """Base class for an integer setting."""

    def from_str(self, value: str) -> Optional[int]:
        self._basic_str_validation(value)
        if not value:
            return None

        try:
            intval = int(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be an integer!")
        self.to_py(intval)
        return intval

    def to_py(self, value: Union[int, _UnsetNone]) -> Union[int, _UnsetNone]:
        self._basic_py_validation(value, int)
        self._validate_bounds(value)
        return value


class Float(_Numeric):

    """Base class for a float setting."""

    def from_str(self, value: str) -> Optional[float]:
        self._basic_str_validation(value)
        if not value:
            return None

        try:
            floatval = float(value)
        except ValueError:
            raise configexc.ValidationError(value, "must be a float!")
        self.to_py(floatval)
        return floatval

    def to_py(
            self,
            value: Union[int, float, _UnsetNone],
    ) -> Union[int, float, _UnsetNone]:
        self._basic_py_validation(value, (int, float))
        self._validate_bounds(value)
        return value


class Perc(_Numeric):

    """A percentage."""

    def to_py(
            self,
            value: Union[float, int, str, _UnsetNone]
    ) -> Union[float, int, _UnsetNone]:
        self._basic_py_validation(value, (float, int, str))
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        if isinstance(value, str):
            value = value.rstrip('%')
            try:
                value = float(value)
            except ValueError:
                raise configexc.ValidationError(
                    value, "must be a valid number!")
        self._validate_bounds(value, suffix='%')
        return value

    def to_str(self, value: Union[None, float, int, str]) -> str:
        if value is None:
            return ''
        elif isinstance(value, str):
            return value
        else:
            return '{}%'.format(value)


class PercOrInt(_Numeric):

    """Percentage or integer.

    Attributes:
        minperc: Minimum value for percentage (inclusive).
        maxperc: Maximum value for percentage (inclusive).
        minint: Minimum value for integer (inclusive).
        maxint: Maximum value for integer (inclusive).
    """

    def __init__(
            self, *,
            minperc: int = None,
            maxperc: int = None,
            minint: int = None,
            maxint: int = None,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(
            minval=minint,
            maxval=maxint,
            none_ok=none_ok,
            completions=completions,
        )
        self.minperc = self._parse_bound(minperc)
        self.maxperc = self._parse_bound(maxperc)
        if (self.maxperc is not None and self.minperc is not None and
                self.maxperc < self.minperc):
            raise ValueError("minperc ({}) needs to be <= maxperc "
                             "({})!".format(self.minperc, self.maxperc))

    def from_str(self, value: str) -> Union[None, str, int]:
        self._basic_str_validation(value)
        if not value:
            return None

        if value.endswith('%'):
            self.to_py(value)
            return value

        try:
            intval = int(value)
        except ValueError:
            raise configexc.ValidationError(value,
                                            "must be integer or percentage!")
        self.to_py(intval)
        return intval

    def to_py(self, value: Union[None, str, int]) -> Union[None, str, int]:
        """Expect a value like '42%' as string, or 23 as int."""
        self._basic_py_validation(value, (int, str))
        if value is None:
            return None

        if isinstance(value, str):
            if not value.endswith('%'):
                raise configexc.ValidationError(
                    value, "needs to end with % or be an integer")

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

            # Note we don't actually return the integer here, as we need to
            # know whether it was a percentage.
        else:
            self._validate_bounds(value)
        return value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, minint=self.minval,
                              maxint=self.maxval, minperc=self.minperc,
                              maxperc=self.maxperc)


class Command(BaseType):

    """A qutebrowser command with arguments.

    //

    Since validation is quite tricky here, we don't do so, and instead let
    invalid commands (in bindings/aliases) fail when used.
    """

    def complete(self) -> _Completions:
        if self._completions is not None:
            return self._completions

        out = []
        for cmdname, obj in objects.commands.items():
            out.append((cmdname, obj.desc))
        return out

    def to_py(self, value: str) -> str:
        self._basic_py_validation(value, str)
        return value


class ColorSystem(MappingType):

    """The color system to use for color interpolation."""

    MAPPING = {
        'rgb': (QColor.Spec.Rgb, "Interpolate in the RGB color system."),
        'hsv': (QColor.Spec.Hsv, "Interpolate in the HSV color system."),
        'hsl': (QColor.Spec.Hsl, "Interpolate in the HSL color system."),
        'none': (None, "Don't show a gradient."),
    }


class IgnoreCase(MappingType):

    """Whether to search case insensitively."""

    MAPPING = {
        'always': (usertypes.IgnoreCase.always, "Search case-insensitively."),
        'never': (usertypes.IgnoreCase.never, "Search case-sensitively."),
        'smart': (
            usertypes.IgnoreCase.smart,
            "Search case-sensitively if there are capital characters."
        ),
    }


class QtColor(BaseType):

    """A color value.

    A value can be in one of the following formats:

    * `#RGB`/`#RRGGBB`/`#AARRGGBB`/`#RRRGGGBBB`/`#RRRRGGGGBBBB`
    * An SVG color name as specified in
      https://www.w3.org/TR/SVG/types.html#ColorKeywords[the W3C specification].
    * transparent (no color)
    * `rgb(r, g, b)` / `rgba(r, g, b, a)` (values 0-255 or percentages)
    * `hsv(h, s, v)` / `hsva(h, s, v, a)` (values 0-255, hue 0-359)
    """

    def _parse_value(self, kind: str, val: str) -> int:
        try:
            return int(val)
        except ValueError:
            pass

        mult = 359.0 if kind == 'h' else 255.0
        if val.endswith('%'):
            val = val[:-1]
            mult /= 100

        try:
            return int(float(val) * mult)
        except ValueError:
            raise configexc.ValidationError(val, "must be a valid color value")

    def to_py(self, value: _StrUnset) -> Union[_UnsetNone, QColor]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        if '(' in value and value.endswith(')'):
            openparen = value.index('(')
            kind = value[:openparen]
            vals = value[openparen+1:-1].split(',')

            converters: dict[str, Callable[..., QColor]] = {
                'rgba': QColor.fromRgb,
                'rgb': QColor.fromRgb,
                'hsva': QColor.fromHsv,
                'hsv': QColor.fromHsv,
            }

            conv = converters.get(kind)
            if not conv:
                raise configexc.ValidationError(
                    value,
                    '{} not in {}'.format(kind, sorted(converters)))

            if len(kind) != len(vals):
                raise configexc.ValidationError(
                    value,
                    'expected {} values for {}'.format(len(kind), kind))

            int_vals = [self._parse_value(kind, val)
                        for kind, val in zip(kind, vals)]
            return conv(*int_vals)

        color = QColor(value)
        if color.isValid():
            return color
        else:
            raise configexc.ValidationError(value, "must be a valid color")


class QssColor(BaseType):

    """A color value supporting gradients.

    A value can be in one of the following formats:

    * `#RGB`/`#RRGGBB`/`#AARRGGBB`/`#RRRGGGBBB`/`#RRRRGGGGBBBB`
    * An SVG color name as specified in
      https://www.w3.org/TR/SVG/types.html#ColorKeywords[the W3C specification].
    * transparent (no color)
    * `rgb(r, g, b)` / `rgba(r, g, b, a)` (values 0-255 or percentages)
    * `hsv(h, s, v)` / `hsva(h, s, v, a)` (values 0-255, hue 0-359)
    * A gradient as explained in
      https://doc.qt.io/qt-6/stylesheet-reference.html#list-of-property-types[the Qt documentation]
      under ``Gradient''
    """

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        functions = ['rgb', 'rgba', 'hsv', 'hsva', 'qlineargradient',
                     'qradialgradient', 'qconicalgradient']
        if (any(value.startswith(func + '(') for func in functions) and
                value.endswith(')')):
            # QColor doesn't handle these
            return value

        if not QColor.isValidColor(value):
            raise configexc.ValidationError(value, "must be a valid color")

        return value


class FontBase(BaseType):

    """Base class for Font/FontFamily."""

    # Gets set when the config is initialized.
    default_family: Optional[str] = None
    default_size: Optional[str] = None
    font_regex = re.compile(r"""
        (
            (
                # style
                (?P<style>normal|italic|oblique) |
                # weight (named | 100..900)
                (
                    (?P<weight>[123456789]00) |
                    (?P<namedweight>normal|bold)
                ) |
                # size (<float>pt | <int>px)
                (?P<size>[0-9]+((\.[0-9]+)?[pP][tT]|[pP][xX])|default_size)
            )\           # size/weight/style are space-separated
        )*               # 0-inf size/weight/style tags
        (?P<family>.+)  # mandatory font family""", re.VERBOSE)

    @classmethod
    def set_defaults(cls, default_family: list[str], default_size: str) -> None:
        """Make sure default_family/default_size are available.

        If the given family value (fonts.default_family in the config) is
        unset, a system-specific default monospace font is used.
        """
        if default_family:
            families = configutils.FontFamilies(default_family)
        else:
            families = configutils.FontFamilies.from_system_default()

        cls.default_family = families.to_str(quote=True)
        cls.default_size = default_size

    def to_py(self, value: Any) -> Any:
        raise NotImplementedError


class Font(FontBase):

    """A font family, with optional style/weight/size.

    * Style: `normal`/`italic`/`oblique`
    * Weight: `normal`, `bold`, `100`..`900`
    * Size: _number_ `px`/`pt`
    """

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        if not self.font_regex.fullmatch(value):  # pragma: no cover
            # This should never happen, as the regex always matches everything
            # as family.
            raise configexc.ValidationError(value, "must be a valid font")

        if (value.endswith(' default_family') and
                self.default_family is not None):
            value = value.replace('default_family', self.default_family)

        if 'default_size ' in value and self.default_size is not None:
            value = value.replace('default_size', self.default_size)

        return value


class FontFamily(FontBase):

    """A Qt font family."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        match = self.font_regex.fullmatch(value)
        if not match:  # pragma: no cover
            # This should never happen, as the regex always matches everything
            # as family.
            raise configexc.ValidationError(value, "must be a valid font")
        for group in 'style', 'weight', 'namedweight', 'size':
            if match.group(group):
                raise configexc.ValidationError(value, "may not include a "
                                                "{}!".format(group))

        return value


class Regex(BaseType):

    """A regular expression.

    When setting from `config.py`, both a string or a `re.compile(...)` object
    are valid.

    Attributes:
        flags: The flags to be used when a string is passed.
        _regex_type: The Python type of a regex object.
    """

    def __init__(
            self, *,
            flags: str = None,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self._regex_type = type(re.compile(''))
        # Parse flags from configdata.yml
        if flags is None:
            self.flags = 0
        else:
            self.flags = functools.reduce(
                operator.or_,
                (getattr(re, flag.strip()) for flag in flags.split(' | ')))

    def _compile_regex(self, pattern: str) -> Pattern[str]:
        """Check if the given regex is valid.

        Some semi-invalid regexes can also raise warnings - we also treat them as
        invalid.
        """
        try:
            with log.py_warning_filter('error', category=FutureWarning):
                compiled = re.compile(pattern, self.flags)
        except (re.error, FutureWarning) as e:
            raise configexc.ValidationError(
                pattern, "must be a valid regex - " + str(e))
        except RuntimeError:  # pragma: no cover
            raise configexc.ValidationError(
                pattern, "must be a valid regex - recursion depth "
                "exceeded")

        return compiled

    def to_py(
            self,
            value: Union[str, Pattern[str], usertypes.Unset]
    ) -> Union[_UnsetNone, Pattern[str]]:
        """Get a compiled regex from either a string or a regex object."""
        self._basic_py_validation(value, (str, self._regex_type))
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None
        elif isinstance(value, str):
            return self._compile_regex(value)
        else:
            return value

    def to_str(self, value: Union[None, str, Pattern[str]]) -> str:
        if value is None:
            return ''
        elif isinstance(value, self._regex_type):
            return value.pattern
        else:
            assert isinstance(value, str)
            return value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, flags=self.flags)


class Dict(BaseType):

    """A dictionary of values.

    When setting from a string, pass a json-like dict, e.g. `{"key", "value"}`.
    """

    def __init__(
            self, *,
            keytype: Union[String, 'Key'],
            valtype: BaseType,
            fixed_keys: Iterable = None,
            required_keys: Iterable = None,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        # If the keytype is not a string, we'll get problems with showing it as
        # json in to_str() as json converts keys to strings.
        assert isinstance(keytype, (String, Key)), keytype
        self.keytype = keytype
        self.valtype = valtype
        self.fixed_keys = fixed_keys
        self.required_keys = required_keys

    def _validate_keys(self, value: dict) -> None:
        if (self.fixed_keys is not None and not
                set(value.keys()).issubset(self.fixed_keys)):
            raise configexc.ValidationError(
                value, "Expected keys {}".format(self.fixed_keys))

        if (self.required_keys is not None and not
                set(self.required_keys).issubset(value.keys())):
            raise configexc.ValidationError(
                value, "Required keys {}".format(self.required_keys))

    def from_str(self, value: str) -> Optional[dict]:
        self._basic_str_validation(value)
        if not value:
            return None

        try:
            yaml_val = utils.yaml_load(value)
        except yaml.YAMLError as e:
            raise configexc.ValidationError(value, str(e))

        # For the values, we actually want to call to_py, as we did parse them
        # from YAML, so they are numbers/booleans/... already.
        self.to_py(yaml_val)
        return yaml_val

    def from_obj(self, value: Optional[dict]) -> dict:
        if value is None:
            return {}

        return {self.keytype.from_obj(key): self.valtype.from_obj(val)
                for key, val in value.items()}

    def _fill_fixed_keys(self, value: dict) -> dict:
        """Fill missing fixed keys with a None-value."""
        if self.fixed_keys is None:
            return value
        for key in self.fixed_keys:
            if key not in value:
                value[key] = self.valtype.to_py(None)
        return value

    def to_py(
            self,
            value: Union[dict, _UnsetNone]
    ) -> Union[dict, usertypes.Unset]:
        self._basic_py_validation(value, dict)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return self._fill_fixed_keys({})

        self._validate_keys(value)
        for key, val in value.items():
            self._validate_surrogate_escapes(value, key)
            self._validate_surrogate_escapes(value, val)

        d = {self.keytype.to_py(key): self.valtype.to_py(val)
             for key, val in value.items()}
        return self._fill_fixed_keys(d)

    def to_str(self, value: dict) -> str:
        if not value:
            # An empty Dict is treated just like None -> empty string
            return ''
        return json.dumps(value, sort_keys=True)

    def to_doc(self, value: dict, indent: int = 0) -> str:
        if not value:
            return 'empty'
        lines = ['\n']
        prefix = '-' if not indent else '*' * indent
        for key, val in sorted(value.items()):
            lines += ('{} {}: {}'.format(
                prefix,
                self.keytype.to_doc(key),
                self.valtype.to_doc(val, indent=indent+1),
            )).splitlines()
        return '\n'.join(line.rstrip(' ') for line in lines)

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, keytype=self.keytype,
                              valtype=self.valtype, fixed_keys=self.fixed_keys,
                              required_keys=self.required_keys)


class File(BaseType):

    """A file on the local filesystem."""

    def __init__(
            self, *,
            required: bool = True,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.required = required

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        value = os.path.expanduser(value)
        value = os.path.expandvars(value)
        try:
            if not os.path.isabs(value):
                value = os.path.join(standarddir.config(), value)

            if self.required and not os.path.isfile(value):
                raise configexc.ValidationError(
                    value,
                    "Must be an existing file (absolute or relative to the "
                    "config directory)!")
        except UnicodeEncodeError as e:
            raise configexc.ValidationError(value, e)

        return value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok,
                              required=self.required)


class Directory(BaseType):

    """A directory on the local filesystem."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None
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

        return value


class FormatString(BaseType):

    """A string with placeholders.

    Attributes:
        fields: Which replacements are allowed in the format string.
        encoding: Which encoding the string should fit into.
        completions: completions to be used, or None
    """

    def __init__(
            self, *,
            fields: Iterable[str],
            none_ok: bool = False,
            encoding: str = None,
            completions: _Completions = None,
    ) -> None:
        super().__init__(
            none_ok=none_ok, completions=completions)
        self.fields = fields
        self.encoding = encoding
        self._completions = completions

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        _validate_encoding(self.encoding, value)

        try:
            value.format(**dict.fromkeys(self.fields, ""))
        except (KeyError, IndexError, AttributeError) as e:
            raise configexc.ValidationError(value, "Invalid placeholder "
                                            "{}".format(e))
        except ValueError as e:
            raise configexc.ValidationError(value, str(e))

        return value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok, fields=self.fields)


class ShellCommand(List):

    """A shell command as a list.

    See the documentation for `List`.

    Attributes:
        placeholder: If there should be a placeholder.
    """

    _show_valtype = False

    def __init__(
            self, *,
            placeholder: bool = False,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(valtype=String(), none_ok=none_ok, completions=completions)
        self.placeholder = placeholder

    def to_py(
            self,
            value: Union[list, usertypes.Unset],
    ) -> Union[list, usertypes.Unset]:
        py_value = super().to_py(value)
        if isinstance(py_value, usertypes.Unset):
            return py_value
        elif not py_value:
            return []

        if (self.placeholder and
                '{}' not in ' '.join(py_value) and
                '{file}' not in ' '.join(py_value)):
            raise configexc.ValidationError(py_value, "needs to contain a "
                                            "{}-placeholder or a "
                                            "{file}-placeholder.")
        return py_value

    def __repr__(self) -> str:
        return utils.get_repr(self, none_ok=self.none_ok,
                              placeholder=self.placeholder)


class Proxy(BaseType):

    """A proxy URL, or `system`/`none`."""

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues(
            ('system', "Use the system wide proxy."),
            ('none', "Don't use any proxy"),
            others_permitted=True,
        )

    def to_py(
            self,
            value: _StrUnset
    ) -> Union[_UnsetNone, QNetworkProxy, _SystemProxy, pac.PACFetcher]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        try:
            if value == 'system':
                return SYSTEM_PROXY

            if value == 'none':
                url = QUrl('direct://')
            else:
                # If we add a special value to valid_values, we need to handle
                # it here!
                assert self.valid_values is not None
                assert value not in self.valid_values, value
                url = QUrl(value)
            return urlutils.proxy_from_url(url)
        except (urlutils.InvalidUrlError, urlutils.InvalidProxyTypeError) as e:
            raise configexc.ValidationError(value, e)

    def complete(self) -> _Completions:
        if self._completions is not None:
            return self._completions

        assert self.valid_values is not None
        out = []
        for val in self.valid_values:
            out.append((val, self.valid_values.descriptions[val]))
        out.append(('http://', 'HTTP proxy URL'))
        out.append(('socks://', 'SOCKS proxy URL'))
        out.append(('socks://localhost:9050/', 'Tor via SOCKS'))
        out.append(('http://localhost:8080/', 'Local HTTP proxy'))
        out.append(('pac+https://example.com/proxy.pac', 'Proxy autoconfiguration file URL'))
        return out


class SearchEngineUrl(BaseType):

    """A search engine URL."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        if not re.search('{(|0|semiquoted|unquoted|quoted)}', value):
            raise configexc.ValidationError(value, "must contain \"{}\"")

        try:
            format_keys = {
                'quoted': "",
                'unquoted': "",
                'semiquoted': "",
            }
            value.format("", **format_keys)
        except (KeyError, IndexError):
            raise configexc.ValidationError(
                value, "may not contain {...} (use {{ and }} for literal {/})")
        except ValueError as e:
            raise configexc.ValidationError(value, str(e))

        return value


class FuzzyUrl(BaseType):

    """A URL which gets interpreted as search if needed."""

    def to_py(self, value: _StrUnset) -> Union[QUrl, _UnsetNone]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        try:
            return urlutils.fuzzy_url(value, do_search=False)
        except urlutils.InvalidUrlError as e:
            raise configexc.ValidationError(value, str(e))


@dataclasses.dataclass
class PaddingValues:

    """Four padding values."""

    top: int
    bottom: int
    left: int
    right: int


class Padding(Dict):

    """Setting for paddings around elements."""

    _show_valtype = False

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(
            keytype=String(),
            valtype=Int(minval=0, none_ok=none_ok),
            fixed_keys=['top', 'bottom', 'left', 'right'],
            none_ok=none_ok,
            completions=completions
        )

    def to_py(  # type: ignore[override]
            self,
            value: Union[dict, _UnsetNone],
    ) -> Union[usertypes.Unset, PaddingValues]:
        d = super().to_py(value)
        if isinstance(d, usertypes.Unset):
            return d

        return PaddingValues(**d)


class Encoding(BaseType):

    """Setting for a python encoding."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None
        try:
            codecs.lookup(value)
        except LookupError:
            raise configexc.ValidationError(value, "is not a valid encoding!")
        return value


class Position(MappingType):

    """The position of the tab bar."""

    MAPPING = {
        'top': (QTabWidget.TabPosition.North, None),
        'bottom': (QTabWidget.TabPosition.South, None),
        'left': (QTabWidget.TabPosition.West, None),
        'right': (QTabWidget.TabPosition.East, None),
    }


class TextAlignment(MappingType):

    """Alignment of text."""

    MAPPING = {
        'left': (Qt.AlignmentFlag.AlignLeft, None),
        'right': (Qt.AlignmentFlag.AlignRight, None),
        'center': (Qt.AlignmentFlag.AlignCenter, None),
    }


class ElidePosition(MappingType):

    """Position of ellipsis in truncated text."""

    MAPPING = {
        'left': (Qt.TextElideMode.ElideLeft, None),
        'right': (Qt.TextElideMode.ElideRight, None),
        'middle': (Qt.TextElideMode.ElideMiddle, None),
        'none': (Qt.TextElideMode.ElideNone, None),
    }


class VerticalPosition(String):

    """The position of the download bar."""

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues('top', 'bottom')


class Url(BaseType):

    """A URL as a string."""

    def to_py(self, value: _StrUnset) -> Union[_UnsetNone, QUrl]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        qurl = QUrl.fromUserInput(value)
        if not qurl.isValid():
            raise configexc.ValidationError(value, "invalid URL - "
                                            "{}".format(qurl.errorString()))
        return qurl


class SessionName(BaseType):

    """The name of a session."""

    def to_py(self, value: _StrUnset) -> _StrUnsetNone:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None
        if value.startswith('_'):
            raise configexc.ValidationError(value, "may not start with '_'!")
        return value


class SelectOnRemove(MappingType):

    """Which tab to select when the focused tab is removed."""

    MAPPING = {
        'prev': (
            QTabBar.SelectionBehavior.SelectLeftTab,
            ("Select the tab which came before the closed one "
             "(left in horizontal, above in vertical)."),
        ),
        'next': (
            QTabBar.SelectionBehavior.SelectRightTab,
            ("Select the tab which came after the closed one "
             "(right in horizontal, below in vertical)."),
        ),
        'last-used': (
            QTabBar.SelectionBehavior.SelectPreviousTab,
            "Select the previously selected tab.",
        ),
    }


class ConfirmQuit(FlagList):

    """Whether to display a confirmation when the window is closed."""

    # Values that can be combined with commas
    combinable_values = ('multiple-tabs', 'downloads')

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valtype.none_ok = none_ok
        self.valtype.valid_values = ValidValues(
            ('always', "Always show a confirmation."),
            ('multiple-tabs', "Show a confirmation if "
             "multiple tabs are opened."),
            ('downloads', "Show a confirmation if "
             "downloads are running"),
            ('never', "Never show a confirmation."))

    def to_py(
            self,
            value: Union[usertypes.Unset, list],
    ) -> Union[list, usertypes.Unset]:
        values = super().to_py(value)
        if isinstance(values, usertypes.Unset):
            return values
        elif not values:
            return []

        # Never can't be set with other options
        if 'never' in values and len(values) > 1:
            raise configexc.ValidationError(
                values, "List cannot contain never!")
        # Always can't be set with other options
        if 'always' in values and len(values) > 1:
            raise configexc.ValidationError(
                values, "List cannot contain always!")

        return values


class NewTabPosition(String):

    """How new tabs are positioned."""

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues(
            ('prev', "Before the current tab."),
            ('next', "After the current tab."),
            ('first', "At the beginning."),
            ('last', "At the end."))


class LogLevel(String):

    """A logging level."""

    def __init__(
            self, *,
            none_ok: bool = False,
            completions: _Completions = None,
    ) -> None:
        super().__init__(none_ok=none_ok, completions=completions)
        self.valid_values = ValidValues(*[level.lower()
                                          for level in log.LOG_LEVELS])


class Key(BaseType):

    """A name of a key."""

    def from_obj(self, value: str) -> str:
        """Make sure key sequences are always normalized."""
        return str(keyutils.KeySequence.parse(value))

    def to_py(
            self,
            value: _StrUnset
    ) -> Union[_UnsetNone, keyutils.KeySequence]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        try:
            return keyutils.KeySequence.parse(value)
        except keyutils.KeyParseError as e:
            raise configexc.ValidationError(value, str(e))


class UrlPattern(BaseType):

    """A match pattern for a URL.

    See
    https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns
    for the allowed syntax.
    """

    def to_py(
            self,
            value: _StrUnset
    ) -> Union[_UnsetNone, urlmatch.UrlPattern]:
        self._basic_py_validation(value, str)
        if isinstance(value, usertypes.Unset):
            return value
        elif not value:
            return None

        try:
            return urlmatch.UrlPattern(value)
        except urlmatch.ParseError as e:
            raise configexc.ValidationError(value, str(e))


class StatusbarWidget(String):

    """A widget for the status bar.

    Allows some predefined widgets and custom text-widgets via text:$CONTENT.
    """

    def _validate_valid_values(self, value: str) -> None:
        if value.startswith("text:") or value.startswith("clock:"):
            return
        super()._validate_valid_values(value)


ConfigType = Union[
    MappingType,
    String,
    UniqueCharString,
    List,
    ListOrValue,
    FlagList,
    Bool,
    BoolAsk,
    Int,
    Float,
    Perc,
    PercOrInt,
    Command,
    ColorSystem,
    IgnoreCase,
    QtColor,
    QssColor,
    Font,
    FontFamily,
    Regex,
    Dict,
    File,
    Directory,
    FormatString,
    ShellCommand,
    Proxy,
    SearchEngineUrl,
    FuzzyUrl,
    Padding,
    Encoding,
    Position,
    TextAlignment,
    ElidePosition,
    VerticalPosition,
    Url,
    SessionName,
    SelectOnRemove,
    ConfirmQuit,
    NewTabPosition,
    LogLevel,
    Key,
    UrlPattern,
    StatusbarWidget
]
"""A union of all possible parsed config types."""
