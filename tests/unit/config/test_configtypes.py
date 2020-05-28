# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configtypes."""

import re
import json
import math
import warnings
import inspect
import functools

import attr
import pytest
import hypothesis
from hypothesis import strategies
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtNetwork import QNetworkProxy

from qutebrowser.misc import objects
from qutebrowser.config import configtypes, configexc
from qutebrowser.utils import debug, utils, qtutils, urlmatch, usertypes
from qutebrowser.browser.network import pac
from qutebrowser.keyinput import keyutils
from helpers import utils as testutils


class Font(QFont):

    """A QFont with a nicer repr()."""

    def __repr__(self):
        weight = debug.qenum_key(QFont, self.weight(), add_base=True,
                                 klass=QFont.Weight)
        kwargs = {
            'family': self.family(),
            'pt': self.pointSize(),
            'px': self.pixelSize(),
            'weight': weight,
            'style': self.style(),
        }
        try:
            kwargs['families'] = self.families()
        except AttributeError:
            # Added in Qt 5.13
            pass

        return utils.get_repr(self, **kwargs)

    @classmethod
    def fromdesc(cls, desc):
        """Get a Font based on a font description."""
        f = cls()

        f.setStyle(desc.style)
        f.setWeight(desc.weight)

        if desc.pt is not None and desc.pt != -1:
            f.setPointSize(desc.pt)
        if desc.px is not None and desc.pt != -1:
            f.setPixelSize(desc.px)

        f.setFamily(desc.family)
        try:
            f.setFamilies([desc.family])
        except AttributeError:
            # Added in Qt 5.13
            pass

        return f


class RegexEq:

    """A class to compare regex objects."""

    def __init__(self, pattern, flags=0):
        # We compile the regex because re.compile also adds flags defined in
        # the pattern and implicit flags to its .flags.
        # See https://docs.python.org/3/library/re.html#re.regex.flags
        compiled = re.compile(pattern, flags)
        self.pattern = compiled.pattern
        self.flags = compiled.flags
        self._user_flags = flags

    def __eq__(self, other):
        try:
            # Works for RegexEq objects and re.compile objects
            return (self.pattern, self.flags) == (other.pattern, other.flags)
        except AttributeError:
            return NotImplemented

    def __repr__(self):
        if self._user_flags:
            return "RegexEq({!r}, flags={})".format(self.pattern,
                                                    self._user_flags)
        else:
            return "RegexEq({!r})".format(self.pattern)


@pytest.fixture
def os_mock(mocker):
    """Fixture that mocks and returns os from the configtypes module."""
    m = mocker.patch('qutebrowser.config.configtypes.os', autospec=True)
    m.path.expandvars.side_effect = lambda x: x.replace('$HOME', '/home/foo')
    m.path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
    m.path.join.side_effect = lambda *parts: '/'.join(parts)
    return m


class TestValidValues:

    @pytest.fixture
    def klass(self):
        return configtypes.ValidValues

    @pytest.mark.parametrize('valid_values, contained, not_contained', [
        # Without description
        (['foo', 'bar'], ['foo'], ['baz']),
        # With description
        ([('foo', "foo desc"), ('bar', "bar desc")], ['foo', 'bar'], ['baz']),
        # With mixed description
        ([('foo', "foo desc"), 'bar'], ['foo', 'bar'], ['baz']),
    ])
    def test_contains(self, klass, valid_values, contained, not_contained):
        """Test __contains___ with various values."""
        vv = klass(*valid_values)
        for elem in contained:
            assert elem in vv
        for elem in not_contained:
            assert elem not in vv

    @pytest.mark.parametrize('valid_values', [
        # With description
        ['foo', 'bar'],
        [('foo', "foo desc"), ('bar', "bar desc")],
        [('foo', "foo desc"), 'bar'],
    ])
    def test_iter_without_desc(self, klass, valid_values):
        """Test __iter__ without a description."""
        vv = klass(*valid_values)
        assert list(vv) == ['foo', 'bar']

    def test_descriptions(self, klass):
        """Test descriptions."""
        vv = klass(('foo', "foo desc"), ('bar', "bar desc"), 'baz')
        assert vv.descriptions['foo'] == "foo desc"
        assert vv.descriptions['bar'] == "bar desc"
        assert 'baz' not in vv.descriptions

    @pytest.mark.parametrize('args, expected', [
        (['a', 'b'], "<qutebrowser.config.configtypes.ValidValues "
                     "descriptions={} values=['a', 'b']>"),
        ([('val', 'desc')], "<qutebrowser.config.configtypes.ValidValues "
                            "descriptions={'val': 'desc'} values=['val']>"),
    ])
    def test_repr(self, klass, args, expected):
        assert repr(klass(*args)) == expected

    def test_empty(self, klass):
        with pytest.raises(ValueError):
            klass()

    @pytest.mark.parametrize('args1, args2, is_equal', [
        (('foo', 'bar'), ('foo', 'bar'), True),
        (('foo', 'bar'), ('foo', 'baz'), False),
        ((('foo', 'foo desc'), ('bar', 'bar desc')),
         (('foo', 'foo desc'), ('bar', 'bar desc')),
         True),
        ((('foo', 'foo desc'), ('bar', 'bar desc')),
         (('foo', 'foo desc'), ('bar', 'bar desc2')),
         False),
    ])
    def test_equal(self, klass, args1, args2, is_equal):
        obj1 = klass(*args1)
        obj2 = klass(*args2)
        assert (obj1 == obj2) == is_equal

    def test_from_dict(self, klass):
        """Test initializing from a list of dicts."""
        vv = klass({'foo': "foo desc"}, {'bar': "bar desc"})
        assert 'foo' in vv
        assert 'bar' in vv
        assert vv.descriptions['foo'] == "foo desc"
        assert vv.descriptions['bar'] == "bar desc"


class TestAll:

    """Various tests which apply to all available config types."""

    def gen_classes():  # pylint: disable=no-method-argument
        """Yield all configtypes classes to test.

        Not a method as it's used in decorators.
        """
        for _name, member in inspect.getmembers(configtypes, inspect.isclass):
            if member in [configtypes.BaseType, configtypes.MappingType,
                          configtypes._Numeric, configtypes.FontBase]:
                pass
            elif (member is configtypes.List or
                  member is configtypes.ListOrValue):
                yield pytest.param(
                    functools.partial(member, valtype=configtypes.Int()),
                    id=member.__name__ + '-Int')
                yield pytest.param(
                    functools.partial(member, valtype=configtypes.Url()),
                    id=member.__name__ + '-Url')
            elif member is configtypes.Dict:
                yield pytest.param(
                    functools.partial(member, keytype=configtypes.String(),
                                      valtype=configtypes.String()),
                    id=member.__name__)
            elif member is configtypes.FormatString:
                yield pytest.param(
                    functools.partial(member, fields=['a', 'b']),
                    id=member.__name__)
            elif issubclass(member, configtypes.BaseType):
                yield member

    @pytest.fixture(autouse=True)
    def patch_aliases(self, config_stub):
        """Patch aliases so Command works."""
        config_stub.val.aliases = {}

    @pytest.fixture(params=list(gen_classes()))
    def klass(self, request):
        return request.param

    @pytest.mark.usefixtures('config_tmpdir')
    @hypothesis.given(strategies.text())
    @hypothesis.example('\x00')
    def test_from_str_hypothesis(self, klass, s):
        typ = klass()
        try:
            val = typ.from_str(s)
        except configexc.ValidationError:
            return

        # For some types, we don't actually get the internal (YAML-like) value
        # back from from_str(), so we can't convert it back.
        if klass in [configtypes.FuzzyUrl, configtypes.QtFont,
                     configtypes.ShellCommand, configtypes.Url]:
            return

        converted = typ.to_str(val)
        # For those we only check that to_str doesn't crash, but we can't be
        # sure we get the 100% same value back.
        if klass in [
                configtypes.Bool,  # on -> true
                configtypes.BoolAsk,  # ditto
                configtypes.Float,  # 1.0 -> 1
                configtypes.Int,  # 00 -> 0
                configtypes.PercOrInt,  # ditto
        ]:
            return
        elif (isinstance(typ, functools.partial) and
              isinstance(typ.func, (configtypes.ListOrValue,
                                    configtypes.List))):
            # ListOrValue: "- /" -> "/"
            # List: "- /" -> ["/"]
            return
        elif (isinstance(typ, configtypes.ListOrValue) and
              isinstance(typ.valtype, configtypes.Int)):
            # "00" -> "0"
            return

        assert converted == s

    def test_none_ok_true(self, klass):
        """Test None and empty string values with none_ok=True."""
        typ = klass(none_ok=True)
        if isinstance(typ, configtypes.Padding):
            to_py_expected = configtypes.PaddingValues(None, None, None, None)
        elif isinstance(typ, configtypes.Dict):
            to_py_expected = {}
        elif isinstance(typ, (configtypes.List, configtypes.ListOrValue)):
            to_py_expected = []
        else:
            to_py_expected = None
        assert typ.from_str('') is None
        assert typ.to_py(None) == to_py_expected
        assert typ.to_str(None) == ''

    @pytest.mark.parametrize('method, value', [
        ('from_str', ''),
        ('to_py', ''),
        ('to_py', None),
    ])
    def test_none_ok_false(self, klass, method, value):
        """Test None and empty string values with none_ok=False."""
        meth = getattr(klass(), method)
        with pytest.raises(configexc.ValidationError):
            meth(value)

    @pytest.mark.parametrize('none_ok', [True, False])
    def test_unset(self, klass, none_ok):
        typ = klass(none_ok=none_ok)
        assert typ.to_py(usertypes.UNSET) is usertypes.UNSET

    def test_to_str_none(self, klass):
        assert klass().to_str(None) == ''

    def test_invalid_python_type(self, klass):
        """Make sure every type fails when passing an invalid Python type."""
        with pytest.raises(configexc.ValidationError):
            klass().to_py(object())

    def test_completion_validity(self, klass):
        """Make sure all completions are actually valid values."""
        typ = klass()
        completions = typ.complete()
        if completions is not None:
            for value, _desc in completions:
                typ.from_str(value)


class TestBaseType:

    @pytest.fixture
    def klass(self):
        return configtypes.BaseType

    def test_validate_valid_values_nop(self, klass):
        """Test validate without valid_values set."""
        klass()._validate_valid_values("foo")

    def test_validate_valid_values(self, klass):
        """Test validate with valid_values set."""
        basetype = klass()
        basetype.valid_values = configtypes.ValidValues('foo', 'bar')
        basetype._validate_valid_values('bar')
        with pytest.raises(configexc.ValidationError):
            basetype._validate_valid_values('baz')

    @pytest.mark.parametrize('val', ['', 'foobar', 'snowman: ☃', 'foo bar'])
    def test_basic_str_validation_valid(self, klass, val):
        """Test _basic_validation with valid values."""
        basetype = klass()
        basetype.none_ok = True
        basetype._basic_str_validation(val)

    @pytest.mark.parametrize('val', ['', '\x00'])
    def test_basic_validation_invalid(self, klass, val):
        """Test _basic_validation with invalid values."""
        with pytest.raises(configexc.ValidationError):
            klass()._basic_str_validation(val)

    def test_basic_py_validation_valid(self, klass):
        klass()._basic_py_validation(['a'], list)

    def test_basic_py_validation_invalid(self, klass):
        with pytest.raises(configexc.ValidationError,
                           match='expected a value of type str but got list'):
            klass()._basic_py_validation([], str)

    def test_basic_py_validation_invalid_str(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass()._basic_py_validation('\x00', str)

    def test_complete_none(self, klass):
        """Test complete with valid_values not set."""
        assert klass().complete() is None

    @pytest.mark.parametrize('valid_values, completions', [
        # Without description
        (['foo', 'bar'],
         [('foo', ''), ('bar', '')]),
        # With description
        ([('foo', "foo desc"), ('bar', "bar desc")],
         [('foo', "foo desc"), ('bar', "bar desc")]),
        # With mixed description
        ([('foo', "foo desc"), 'bar'],
         [('foo', "foo desc"), ('bar', "")]),
    ])
    def test_complete_without_desc(self, klass, valid_values, completions):
        """Test complete with valid_values set without description."""
        basetype = klass()
        basetype.valid_values = configtypes.ValidValues(*valid_values)
        assert basetype.complete() == completions

    def test_get_name(self, klass):
        assert klass().get_name() == 'BaseType'

    def test_get_valid_values(self, klass):
        basetype = klass()
        basetype.valid_values = configtypes.ValidValues('foo')
        assert basetype.get_valid_values() is basetype.valid_values

    @pytest.mark.parametrize('value, expected', [
        ('hello', '+pass:[hello]+'),
        ('', 'empty'),
        ('<', '+pass:[&lt;]+'),
    ])
    def test_to_doc(self, klass, value, expected):
        assert klass().to_doc(value) == expected

    @pytest.mark.parametrize('obj', [42, '', None, 'foo'])
    def test_from_obj(self, klass, obj):
        assert klass(none_ok=True).from_obj(obj) == obj


class MappingSubclass(configtypes.MappingType):

    """A MappingType we use in TestMappingType which is valid/good."""

    MAPPING = {
        'one': 1,
        'two': 2,
    }

    def __init__(self, none_ok=False):
        super().__init__(none_ok)
        self.valid_values = configtypes.ValidValues('one', 'two')


class TestMappingType:

    TESTS = {
        'one': 1,
        'two': 2,
        'ONE': 1,
    }

    @pytest.fixture
    def klass(self):
        return MappingSubclass

    @pytest.mark.parametrize('val, expected', list(TESTS.items()))
    def test_to_py_valid(self, klass, val, expected):
        assert klass().to_py(val) == expected

    @pytest.mark.parametrize('val', ['one!', 'blah'])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    def test_to_str(self, klass):
        assert klass().to_str('one') == 'one'

    @pytest.mark.parametrize('typ', [configtypes.ColorSystem(),
                                     configtypes.Position(),
                                     configtypes.SelectOnRemove()])
    def test_mapping_type_matches_valid_values(self, typ):
        assert sorted(typ.MAPPING) == sorted(typ.valid_values)


class TestString:

    @pytest.fixture(params=[configtypes.String, configtypes.UniqueCharString])
    def klass(self, request):
        return request.param

    @pytest.mark.parametrize('minlen, maxlen', [(1, None), (None, 1)])
    def test_lengths_valid(self, klass, minlen, maxlen):
        klass(minlen=minlen, maxlen=maxlen)

    @pytest.mark.parametrize('minlen, maxlen', [
        (0, None),  # minlen too small
        (None, 0),  # maxlen too small
        (2, 1),  # maxlen < minlen
    ])
    def test_lengths_invalid(self, klass, minlen, maxlen):
        with pytest.raises(ValueError):
            klass(minlen=minlen, maxlen=maxlen)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, "Test! :-)"),
        # Forbidden chars
        ({'forbidden': 'xyz'}, 'fobar'),
        ({'forbidden': 'xyz'}, 'foXbar'),
        # Lengths
        ({'minlen': 2}, 'fo'),
        ({'minlen': 2, 'maxlen': 3}, 'fo'),
        ({'minlen': 2, 'maxlen': 3}, 'abc'),
        # valid_values
        ({'valid_values': configtypes.ValidValues('abcd')}, 'abcd'),
        # Surrogate escapes are allowed in strings
        ({}, '\U00010000'),
        # Regex
        ({'regex': '[aA]'}, 'a'),
    ])
    def test_to_py_valid(self, klass, kwargs, val):
        assert klass(**kwargs).to_py(val) == val

    @pytest.mark.parametrize('kwargs, val', [
        # Forbidden chars
        ({'forbidden': 'xyz'}, 'foybar'),
        ({'forbidden': 'xyz'}, 'foxbar'),
        # Lengths
        ({'minlen': 2}, 'f'),
        ({'maxlen': 2}, 'fob'),
        ({'minlen': 2, 'maxlen': 3}, 'f'),
        ({'minlen': 2, 'maxlen': 3}, 'abcd'),
        # valid_values
        ({'valid_values': configtypes.ValidValues('blah')}, 'abcd'),
        # Encoding
        ({'encoding': 'ascii'}, 'fooäbar'),
        # Regex
        ({'regex': '[aA]'}, 'abc'),
    ])
    def test_to_py_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).to_py(val)

    def test_to_py_duplicate_invalid(self):
        typ = configtypes.UniqueCharString()
        with pytest.raises(configexc.ValidationError):
            typ.to_py('foobar')

    @pytest.mark.parametrize('value', [
        None,
        ['one', 'two'],
        [('1', 'one'), ('2', 'two')],
    ])
    def test_complete(self, klass, value):
        assert klass(completions=value).complete() == value

    @pytest.mark.parametrize('valid_values, expected', [
        (configtypes.ValidValues('one', 'two'),
         [('one', ''), ('two', '')]),
        (configtypes.ValidValues(('1', 'one'), ('2', 'two')),
         [('1', 'one'), ('2', 'two')]),
    ])
    def test_complete_valid_values(self, klass, valid_values, expected):
        assert klass(valid_values=valid_values).complete() == expected


class ListSubclass(configtypes.List):

    """A subclass of List which we use in tests. Similar to FlagList.

    Valid values are 'foo', 'bar' and 'baz'.
    """

    def __init__(self, none_ok_inner=False, none_ok_outer=False, length=None,
                 elemtype=None, set_valid_values=False):
        if elemtype is None:
            elemtype = configtypes.String(none_ok=none_ok_inner)
        super().__init__(elemtype, none_ok=none_ok_outer, length=length)
        if set_valid_values:
            self.valtype.valid_values = configtypes.ValidValues(
                'foo', 'bar', 'baz')


class FlagListSubclass(configtypes.FlagList):

    """A subclass of FlagList which we use in tests.

    Valid values are 'foo', 'bar' and 'baz'.
    """

    combinable_values = ['foo', 'bar']

    def __init__(self, none_ok_inner=False, none_ok_outer=False, length=None,
                 set_valid_values=False):
        # none_ok_inner is ignored, just here for compatibility with TestList
        super().__init__(none_ok=none_ok_outer, length=length)
        if set_valid_values:
            self.valtype.valid_values = configtypes.ValidValues(
                'foo', 'bar', 'baz')


class FromObjType(configtypes.BaseType):

    """Config type to test from_obj for List/Dict."""

    def from_obj(self, value):
        return int(value)

    def to_py(self, value):
        return value


class TestList:

    """Test List and FlagList."""

    @pytest.fixture(params=[ListSubclass, FlagListSubclass])
    def klass(self, request):
        return request.param

    @pytest.mark.parametrize('val', [['foo'], ['foo', 'bar']])
    def test_from_str(self, klass, val):
        json_val = json.dumps(val)
        assert klass().from_str(json_val) == val

    def test_from_str_int(self):
        typ = configtypes.List(valtype=configtypes.Int())
        assert typ.from_str(json.dumps([0])) == [0]

    @pytest.mark.parametrize('val', ['[[', 'true', '[]'])
    def test_from_str_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().from_str(val)

    @pytest.mark.parametrize('obj, expected', [
        ([1], [1]),
        ([], []),
        (None, []),
    ])
    def test_from_obj(self, klass, obj, expected):
        assert klass(none_ok_outer=True).from_obj(obj) == expected

    @pytest.mark.parametrize('val', [['foo'], ['foo', 'bar']])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    @pytest.mark.parametrize('val', [[42], '["foo"]', ['\U00010000']])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    def test_to_py_invalid_valid_values(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass(set_valid_values=True).to_py(['invalid'])

    def test_invalid_empty_value_none_ok(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass(none_ok_outer=True).to_py(['foo', '', 'bar'])
        with pytest.raises(configexc.ValidationError):
            klass(none_ok_inner=True).to_py(None)

    @pytest.mark.parametrize('val', [None, ['foo', 'bar']])
    def test_to_py_length(self, klass, val):
        klass(none_ok_outer=True, length=2).to_py(val)

    @pytest.mark.parametrize('val', [['a'], ['a', 'b'], ['a', 'b', 'c', 'd']])
    def test_wrong_length(self, klass, val):
        with pytest.raises(configexc.ValidationError,
                           match='Exactly 3 values need to be set!'):
            klass(length=3).to_py(val)

    def test_get_name(self, klass):
        expected = {
            ListSubclass: 'ListSubclass of String',
            FlagListSubclass: 'FlagListSubclass',
        }
        assert klass().get_name() == expected[klass]

    def test_get_valid_values(self, klass):
        expected = configtypes.ValidValues('foo', 'bar', 'baz')
        assert klass(set_valid_values=True).get_valid_values() == expected

    def test_to_str(self, klass):
        assert klass().to_str(["a", True]) == '["a", true]'

    @hypothesis.given(val=strategies.lists(strategies.just('foo')))
    def test_hypothesis(self, klass, val):
        typ = klass(none_ok_outer=True)
        try:
            converted = typ.to_py(val)
        except configexc.ValidationError:
            pass
        else:
            expected = converted if converted else None
            assert typ.from_str(typ.to_str(converted)) == expected

    @hypothesis.given(val=strategies.lists(strategies.just('foo')))
    def test_hypothesis_text(self, klass, val):
        typ = klass()
        text = json.dumps(val)
        try:
            converted = typ.from_str(text)
        except configexc.ValidationError:
            pass
        else:
            expected = '' if not val else text
            assert typ.to_str(converted) == expected

    @pytest.mark.parametrize('val, expected', [
        # simple list
        (['foo', 'bar'], '\n\n- +pass:[foo]+\n- +pass:[bar]+'),
        # empty
        ([], 'empty'),
    ])
    def test_to_doc(self, klass, val, expected):
        doc = klass().to_doc(val)
        print(doc)
        assert doc == expected

    def test_to_doc_unimplemented(self):
        """List.to_doc with another Dict/List is not implemented."""
        valtype = configtypes.List(valtype=configtypes.String())
        typ = configtypes.List(valtype=valtype)
        with pytest.raises(AssertionError):
            typ.to_doc([['foo']])

    def test_from_obj_sub(self):
        """Make sure the list calls from_obj() on sub-types."""
        typ = configtypes.List(valtype=FromObjType())
        value = typ.from_obj(['1', '2'])
        assert value == [1, 2]


class TestFlagList:

    @pytest.fixture
    def klass(self):
        return FlagListSubclass

    @pytest.mark.parametrize('val', [['qux'], ['foo', 'qux'], ['foo', 'foo']])
    def test_to_py_invalid(self, klass, val):
        """Test invalid flag combinations (the rest is tested in TestList)."""
        typ = klass(none_ok_outer=True, set_valid_values=True)
        with pytest.raises(configexc.ValidationError):
            typ.to_py(val)

    def test_complete(self, klass):
        """Test completing by doing some samples."""
        typ = klass(set_valid_values=True)
        completions = [json.loads(e[0]) for e in typ.complete()]
        assert ['foo'] in completions
        assert ['bar'] in completions
        assert ['baz'] in completions
        assert ['foo', 'bar'] in completions
        for val in completions:
            if len(val) > 1:
                assert 'baz' not in val

    def test_complete_all_valid_values(self, klass):
        typ = klass(set_valid_values=True)
        typ.combinable_values = None
        completions = [json.loads(e[0]) for e in typ.complete()]
        assert ['foo'] in completions
        assert ['bar'] in completions
        assert ['baz'] in completions
        assert ['foo', 'bar'] in completions
        assert ['foo', 'baz'] in completions

    def test_complete_no_valid_values(self, klass):
        assert klass().complete() is None


class TestListOrValue:

    @pytest.fixture
    def klass(self):
        return configtypes.ListOrValue

    @pytest.fixture
    def strtype(self):
        return configtypes.String()

    @pytest.mark.parametrize('val, expected', [
        ('["foo"]', ['foo']),
        ('["foo", "bar"]', ['foo', 'bar']),
        ('foo', 'foo'),
    ])
    def test_from_str(self, klass, strtype, val, expected):
        assert klass(strtype).from_str(val) == expected

    def test_from_str_invalid(self, klass):
        valtype = configtypes.String(minlen=10)
        with pytest.raises(configexc.ValidationError):
            klass(valtype).from_str('123')

    @pytest.mark.parametrize('val, expected', [
        (['foo'], ['foo']),
        ('foo', ['foo']),
    ])
    def test_to_py_valid(self, klass, strtype, val, expected):
        assert klass(strtype).to_py(val) == expected

    @pytest.mark.parametrize('val', [[42], ['\U00010000']])
    def test_to_py_invalid(self, klass, strtype, val):
        with pytest.raises(configexc.ValidationError):
            klass(strtype).to_py(val)

    @pytest.mark.parametrize('val', [None, ['foo', 'bar'], 'abcd'])
    def test_to_py_length(self, strtype, klass, val):
        klass(strtype, none_ok=True, length=2).to_py(val)

    @pytest.mark.parametrize('obj, expected', [
        (['a'], ['a']),
        ([], []),
        (None, []),
    ])
    def test_from_obj(self, klass, obj, expected):
        typ = klass(none_ok=True, valtype=configtypes.String())
        assert typ.from_obj(obj) == expected

    @pytest.mark.parametrize('val', [['a'], ['a', 'b'], ['a', 'b', 'c', 'd']])
    def test_wrong_length(self, strtype, klass, val):
        with pytest.raises(configexc.ValidationError,
                           match='Exactly 3 values need to be set!'):
            klass(strtype, length=3).to_py(val)

    def test_get_name(self, strtype, klass):
        assert klass(strtype).get_name() == 'List of String, or String'

    def test_get_valid_values(self, klass):
        valid_values = configtypes.ValidValues('foo', 'bar', 'baz')
        valtype = configtypes.String(valid_values=valid_values)
        assert klass(valtype).get_valid_values() == valid_values

    def test_to_str(self, strtype, klass):
        assert klass(strtype).to_str(["a", True]) == '["a", true]'

    @hypothesis.given(val=strategies.lists(strategies.just('foo')))
    def test_hypothesis(self, strtype, klass, val):
        typ = klass(strtype, none_ok=True)
        try:
            converted = typ.to_py(val)
        except configexc.ValidationError:
            pass
        else:
            expected = converted if converted else []
            assert typ.to_py(typ.from_str(typ.to_str(converted))) == expected

    @hypothesis.given(val=strategies.lists(strategies.just('foo')))
    def test_hypothesis_text(self, strtype, klass, val):
        typ = klass(strtype)
        text = json.dumps(val)
        try:
            typ.to_str(typ.from_str(text))
        except configexc.ValidationError:
            pass

    @pytest.mark.parametrize('val, expected', [
        # simple list
        (['foo', 'bar'], '\n\n- +pass:[foo]+\n- +pass:[bar]+'),
        # only one value
        (['foo'], '+pass:[foo]+'),
        # value without list
        ('foo', '+pass:[foo]+'),
        # empty
        ([], 'empty'),
        (None, 'empty'),
    ])
    def test_to_doc(self, klass, strtype, val, expected):
        doc = klass(strtype).to_doc(val)
        print(doc)
        assert doc == expected


class TestBool:

    TESTS = {
        '1': True,
        'yes': True,
        'YES': True,
        'true': True,
        'TrUe': True,
        'on': True,

        '0': False,
        'no': False,
        'NO': False,
        'false': False,
        'FaLsE': False,
        'off': False,
    }

    INVALID = ['10', 'yess', 'false_']

    @pytest.fixture
    def klass(self):
        return configtypes.Bool

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_from_str_valid(self, klass, val, expected):
        assert klass().from_str(val) == expected

    @pytest.mark.parametrize('val', INVALID)
    def test_from_str_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().from_str(val)

    @pytest.mark.parametrize('val', [True, False])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) is val

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(42)

    @pytest.mark.parametrize('val, expected', [
        (True, 'true'),
        (False, 'false'),
    ])
    def test_to_str(self, klass, val, expected):
        assert klass().to_str(val) == expected

    @pytest.mark.parametrize('value, expected', [(True, '+pass:[true]+'),
                                                 (False, '+pass:[false]+')])
    def test_to_doc(self, klass, value, expected):
        assert klass().to_doc(value) == expected


class TestBoolAsk:

    TESTS = {
        'ask': 'ask',
        'ASK': 'ask',
    }
    TESTS.update(TestBool.TESTS)

    INVALID = TestBool.INVALID

    @pytest.fixture
    def klass(self):
        return configtypes.BoolAsk

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_from_str_valid(self, klass, val, expected):
        assert klass().from_str(val) == expected

    @pytest.mark.parametrize('val', INVALID)
    def test_from_str_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().from_str(val)

    @pytest.mark.parametrize('val', [True, False, 'ask'])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(42)

    @pytest.mark.parametrize('val, expected', [
        (True, 'true'),
        (False, 'false'),
        ('ask', 'ask'),
    ])
    def test_to_str(self, klass, val, expected):
        assert klass().to_str(val) == expected


class TestNumeric:

    """Test the bounds handling in _Numeric."""

    @pytest.fixture
    def klass(self):
        return configtypes._Numeric

    def test_minval_gt_maxval(self, klass):
        with pytest.raises(ValueError):
            klass(minval=2, maxval=1)

    def test_special_bounds(self, klass):
        """Test passing strings as bounds."""
        numeric = klass(minval='maxint', maxval='maxint64')
        assert numeric.minval == qtutils.MAXVALS['int']
        assert numeric.maxval == qtutils.MAXVALS['int64']

    @pytest.mark.parametrize('kwargs, val, valid', [
        ({}, 1337, True),
        ({}, 0, True),
        ({'minval': 2}, 2, True),
        ({'maxval': 2}, 2, True),
        ({'minval': 2, 'maxval': 3}, 2, True),
        ({'minval': 2, 'maxval': 3}, 3, True),
        ({}, None, True),

        ({'minval': 2}, 1, False),
        ({'maxval': 2}, 3, False),
        ({'minval': 2, 'maxval': 3}, 1, False),
        ({'minval': 2, 'maxval': 3}, 4, False),

        ({'zero_ok': False}, 0, False),
        ({'minval': -1}, 0, True),
    ])
    def test_validate_bounds_invalid(self, klass, kwargs, val, valid):
        if valid:
            klass(**kwargs)._validate_bounds(val)
        else:
            with pytest.raises(configexc.ValidationError):
                klass(**kwargs)._validate_bounds(val)

    def test_suffix(self, klass):
        """Test suffix in validation message."""
        with pytest.raises(configexc.ValidationError,
                           match='must be 2% or smaller'):
            klass(maxval=2)._validate_bounds(3, suffix='%')


class TestInt:

    @pytest.fixture
    def klass(self):
        return configtypes.Int

    @pytest.mark.parametrize('kwargs, val, expected', [
        ({}, '1337', 1337),
        ({}, '0', 0),
        ({'minval': 2}, '2', 2),
    ])
    def test_from_str_valid(self, klass, kwargs, val, expected):
        assert klass(**kwargs).from_str(val) == expected

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '2.5'),
        ({}, 'foobar'),
        ({'minval': 2, 'maxval': 3}, '1'),
    ])
    def test_from_str_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).from_str(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 1337),
        ({}, 0),
        ({'minval': 2}, 2),
    ])
    def test_to_py_valid(self, klass, kwargs, val):
        assert klass(**kwargs).to_py(val) == val

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 2.5),
        ({}, 'foobar'),
        ({'minval': 2, 'maxval': 3}, 1),
        ({}, True),
    ])
    def test_to_py_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).to_py(val)

    @hypothesis.given(val=strategies.integers())
    def test_hypothesis(self, klass, val):
        typ = klass()
        converted = typ.to_py(val)
        assert typ.from_str(typ.to_str(converted)) == converted

    @hypothesis.given(val=strategies.integers())
    def test_hypothesis_text(self, klass, val):
        text = json.dumps(val)
        typ = klass()
        converted = typ.from_str(text)
        assert typ.to_str(converted) == text

    def test_bounds_handling_unset(self, klass):
        typ = klass(minval=1, maxval=2)
        assert typ.to_py(usertypes.UNSET) is usertypes.UNSET


class TestFloat:

    @pytest.fixture
    def klass(self):
        return configtypes.Float

    @pytest.mark.parametrize('kwargs, val, expected', [
        ({}, '1337', 1337),
        ({}, '1337.42', 1337.42),
        ({'minval': 2.00}, '2.00', 2.00),
    ])
    def test_from_str_valid(self, klass, kwargs, val, expected):
        assert klass(**kwargs).from_str(val) == expected

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 'foobar'),
        ({'minval': 2, 'maxval': 3}, '3.01'),
    ])
    def test_from_str_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).from_str(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 1337),
        ({}, 0),
        ({}, 1337.42),
        ({'minval': 2}, 2.01),
    ])
    def test_to_py_valid(self, klass, kwargs, val):
        assert klass(**kwargs).to_py(val) == val

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 'foobar'),
        ({'minval': 2, 'maxval': 3}, 1.99),
    ])
    def test_to_py_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).to_py(val)

    @hypothesis.given(val=strategies.one_of(strategies.floats(),
                                            strategies.integers()))
    def test_hypothesis(self, klass, val):
        typ = klass()
        converted = typ.to_py(val)
        converted_2 = typ.from_str(typ.to_str(converted))
        if math.isnan(converted):
            assert math.isnan(converted_2)
        else:
            assert converted == pytest.approx(converted_2)

    @hypothesis.given(val=strategies.one_of(strategies.floats(),
                                            strategies.integers()))
    def test_hypothesis_text(self, klass, val):
        text = json.dumps(val)
        klass().from_str(text)
        # Can't check for string equality with to_str here, as we can get 1.0
        # for 1.


class TestPerc:

    @pytest.fixture
    def klass(self):
        return configtypes.Perc

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337%'),
        ({}, '1337'),
        ({}, '1337.42%'),
        ({}, '1337.42'),
        ({'maxval': 2}, '2%'),
    ])
    def test_from_str_valid(self, klass, kwargs, val):
        assert klass(**kwargs).from_str(val) == val

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 'foobar'),
        ({}, 'foobar%'),
        ({'minval': 2}, '1%'),
        ({'maxval': 2}, '3%'),
        ({'maxval': 2}, '3'),
        ({'minval': 2, 'maxval': 3}, '1%'),
        ({'minval': 2, 'maxval': 3}, '4%'),
    ])
    def test_from_str_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).from_str(val)

    @pytest.mark.parametrize('kwargs, val, expected', [
        ({}, '1337.42%', 1337.42),
        ({}, '1337.42', 1337.42),
        ({}, 23, 23),
        ({}, 23.42, 23.42),
        ({'minval': 2}, '2.01%', 2.01),
    ])
    def test_to_py_valid(self, klass, kwargs, val, expected):
        assert klass(**kwargs).to_py(val) == expected

    @pytest.mark.parametrize('kwargs, val', [
        ({}, 'foobar'),
        ({'minval': 2, 'maxval': 3}, '1.99%'),
        ({'minval': 2, 'maxval': 3}, '1.99'),
    ])
    def test_to_py_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).to_py(val)

    @pytest.mark.parametrize('value, expected', [
        ('42%', '42%'),
        (42, '42%'),
        (42.5, '42.5%'),
    ])
    def test_to_str(self, klass, value, expected):
        assert klass().to_str(value) == expected


class TestPercOrInt:

    @pytest.fixture
    def klass(self):
        return configtypes.PercOrInt

    def test_minperc_gt_maxperc(self, klass):
        with pytest.raises(ValueError):
            klass(minperc=2, maxperc=1)

    def test_special_bounds(self, klass):
        """Test passing strings as bounds."""
        poi = klass(minperc='maxint', maxperc='maxint64')
        assert poi.minperc == qtutils.MAXVALS['int']
        assert poi.maxperc == qtutils.MAXVALS['int64']

    @pytest.mark.parametrize('kwargs, val, expected', [
        ({}, '1337%', '1337%'),
        ({}, '1337', 1337),

        ({'minperc': 2}, '2%', '2%'),
        ({'maxperc': 2}, '2%', '2%'),
        ({'minperc': 2, 'maxperc': 3}, '2%', '2%'),
        ({'minperc': 2, 'maxperc': 3}, '3%', '3%'),

        ({'minperc': 2, 'maxperc': 3}, '1', 1),
        ({'minperc': 2, 'maxperc': 3}, '4', 4),
        ({'minint': 2, 'maxint': 3}, '1%', '1%'),
        ({'minint': 2, 'maxint': 3}, '4%', '4%'),
    ])
    def test_from_str_valid(self, klass, kwargs, val, expected):
        assert klass(**kwargs).from_str(val) == expected

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337%%'),
        ({}, '1337.42%'),
        ({}, 'foobar'),

        ({'minperc': 2}, '1%'),
        ({'maxperc': 2}, '3%'),
        ({'minperc': 2, 'maxperc': 3}, '1%'),
        ({'minperc': 2, 'maxperc': 3}, '4%'),

        ({'minint': 2}, '1'),
        ({'maxint': 2}, '3'),
        ({'minint': 2, 'maxint': 3}, '1'),
        ({'minint': 2, 'maxint': 3}, '4'),
    ])
    def test_from_str_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).from_str(val)

    @pytest.mark.parametrize('val', ['1337%', 1337])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    @pytest.mark.parametrize('val', ['1337%%', '1337'])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    @hypothesis.given(val=strategies.one_of(
        strategies.integers(),
        strategies.integers().map(lambda n: str(n) + '%'),
        strategies.text()))
    def test_hypothesis(self, klass, val):
        typ = klass(none_ok=True)
        try:
            converted = typ.to_py(val)
        except configexc.ValidationError:
            pass
        else:
            assert typ.from_str(typ.to_str(converted)) == converted

    @hypothesis.given(text=strategies.one_of(
        strategies.integers().map(str),
        strategies.integers().map(lambda n: str(n) + '%')))
    def test_hypothesis_text(self, klass, text):
        typ = klass()
        try:
            converted = typ.from_str(text)
        except configexc.ValidationError:
            pass
        else:
            assert typ.to_str(converted) == text


class TestCommand:

    @pytest.fixture
    def patch_cmdutils(self, monkeypatch, stubs):
        """Patch the cmdutils module to provide fake commands."""
        commands = {
            'cmd1': stubs.FakeCommand(desc="desc 1"),
            'cmd2': stubs.FakeCommand(desc="desc 2"),
        }
        monkeypatch.setattr(objects, 'commands', commands)

    @pytest.fixture
    def klass(self):
        return configtypes.Command

    def test_complete(self, patch_cmdutils, klass):
        """Test completion."""
        items = klass().complete()
        assert len(items) == 2
        assert ('cmd1', "desc 1") in items
        assert ('cmd2', "desc 2") in items


class TestQtColor:

    @pytest.fixture
    def klass(self):
        return configtypes.QtColor

    @pytest.mark.parametrize('val, expected', [
        ('#123', QColor('#123')),
        ('#112233', QColor('#112233')),
        ('#111222333', QColor('#111222333')),
        ('#111122223333', QColor('#111122223333')),
        ('red', QColor('red')),

        ('rgb(0, 0, 0)', QColor.fromRgb(0, 0, 0)),
        ('rgb(0,0,0)', QColor.fromRgb(0, 0, 0)),

        ('rgba(255, 255, 255, 1.0)', QColor.fromRgb(255, 255, 255, 255)),

        ('hsv(10%,10%,10%)', QColor.fromHsv(35, 25, 25)),
        ('hsva(10%,20%,30%,40%)', QColor.fromHsv(35, 51, 76, 102)),
    ])
    def test_valid(self, klass, val, expected):
        assert klass().to_py(val) == expected

    @pytest.mark.parametrize('val,msg', [
        ('#00000G', 'must be a valid color'),
        ('#123456789ABCD', 'must be a valid color'),
        ('#12', 'must be a valid color'),
        ('foobar', 'must be a valid color'),
        ('42', 'must be a valid color'),
        ('foo(1, 2, 3)', "foo not in ['hsv', 'hsva', 'rgb', 'rgba']"),
        ('rgb(1, 2, 3', 'must be a valid color'),
        ('rgb)', 'must be a valid color'),
        ('rgb(1, 2, 3))', 'must be a valid color value'),
        ('rgb((1, 2, 3)', 'must be a valid color value'),
        ('rgb()', 'expected 3 values for rgb'),
        ('rgb(1, 2, 3, 4)', 'expected 3 values for rgb'),
        ('rgba(1, 2, 3)', 'expected 4 values for rgba'),
        ('rgb(10%%, 0, 0)', 'must be a valid color value'),
    ])
    def test_invalid(self, klass, val, msg):
        with pytest.raises(configexc.ValidationError) as excinfo:
            klass().to_py(val)
        assert str(excinfo.value).endswith(msg)


class TestQssColor:

    @pytest.fixture
    def klass(self):
        return configtypes.QssColor

    @pytest.mark.parametrize('val', [
        '#123',
        '#112233',
        '#111222333',
        '#111122223333',
        'red',

        'rgb(0, 0, 0)',
        'rgb(0,0,0)',

        'rgba(255, 255, 255, 1.0)',
        'hsv(10%,10%,10%)',

        'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 white, '
        'stop: 0.4 gray, stop:1 green)',

        'qconicalgradient(cx:0.5, cy:0.5, angle:30, stop:0 white, '
        'stop:1 #00FF00)',

        'qradialgradient(cx:0, cy:0, radius: 1, fx:0.5, fy:0.5, '
        'stop:0 white, stop:1 green)',
    ])
    def test_valid(self, klass, val):
        assert klass().to_py(val) == val

    @pytest.mark.parametrize('val', [
        '#00000G',
        '#123456789ABCD',
        '#12',
        'foobar',
        '42',
        'foo(1, 2, 3)',
        'rgb(1, 2, 3',
    ])
    def test_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


@attr.s
class FontDesc:

    style = attr.ib()
    weight = attr.ib()
    pt = attr.ib()
    px = attr.ib()
    family = attr.ib()


class TestFont:

    """Test Font/QtFont."""

    TESTS = {
        # (style, weight, pointsize, pixelsize, family
        '"Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, -1, -1, 'Foobar Neue'),
        'inconsolatazi4':
            FontDesc(QFont.StyleNormal, QFont.Normal, -1, -1,
                     'inconsolatazi4'),
        'Terminus (TTF)':
            FontDesc(QFont.StyleNormal, QFont.Normal, -1, -1,
                     'Terminus (TTF)'),
        '10pt "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, 10, None, 'Foobar Neue'),
        '10PT "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, 10, None, 'Foobar Neue'),
        '10px "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, None, 10, 'Foobar Neue'),
        '10PX "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, None, 10, 'Foobar Neue'),
        'bold "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Bold, -1, -1, 'Foobar Neue'),
        'italic "Foobar Neue"':
            FontDesc(QFont.StyleItalic, QFont.Normal, -1, -1, 'Foobar Neue'),
        'oblique "Foobar Neue"':
            FontDesc(QFont.StyleOblique, QFont.Normal, -1, -1, 'Foobar Neue'),
        'normal bold "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Bold, -1, -1, 'Foobar Neue'),
        'bold italic "Foobar Neue"':
            FontDesc(QFont.StyleItalic, QFont.Bold, -1, -1, 'Foobar Neue'),
        'bold 10pt "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Bold, 10, None, 'Foobar Neue'),
        'italic 10pt "Foobar Neue"':
            FontDesc(QFont.StyleItalic, QFont.Normal, 10, None, 'Foobar Neue'),
        'oblique 10pt "Foobar Neue"':
            FontDesc(QFont.StyleOblique, QFont.Normal, 10, None,
                     'Foobar Neue'),
        'normal bold 10pt "Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Bold, 10, None, 'Foobar Neue'),
        'bold italic 10pt "Foobar Neue"':
            FontDesc(QFont.StyleItalic, QFont.Bold, 10, None, 'Foobar Neue'),
        'normal 300 10pt "Foobar Neue"':
            FontDesc(QFont.StyleNormal, 37, 10, None, 'Foobar Neue'),
        'normal 800 10pt "Foobar Neue"':
            FontDesc(QFont.StyleNormal, 99, 10, None, 'Foobar Neue'),
    }

    font_xfail = pytest.mark.xfail(reason='FIXME: #103')

    @pytest.fixture(params=[configtypes.Font, configtypes.QtFont])
    def klass(self, request):
        return request.param

    @pytest.fixture
    def font_class(self):
        return configtypes.Font

    @pytest.fixture
    def qtfont_class(self):
        return configtypes.QtFont

    @pytest.mark.parametrize('val, desc', sorted(TESTS.items()))
    def test_to_py_valid(self, klass, val, desc):
        if klass is configtypes.Font:
            expected = val
        elif klass is configtypes.QtFont:
            expected = Font.fromdesc(desc)
        assert klass().to_py(val) == expected

    def test_qtfont(self, qtfont_class):
        """Test QtFont's to_py."""
        value = Font(qtfont_class().to_py('10pt "Foobar Neue", Fubar'))

        if hasattr(value, 'families'):
            # Added in Qt 5.13
            assert value.family() == 'Foobar Neue'
            assert value.families() == ['Foobar Neue', 'Fubar']
        else:
            assert value.family() == 'Foobar Neue, Fubar'

        assert value.weight() == QFont.Normal
        assert value.style() == QFont.StyleNormal

        assert value.pointSize() == 10

    def test_qtfont_float(self, qtfont_class):
        """Test QtFont's to_py with a float as point size.

        We can't test the point size for equality as Qt seems to do some
        rounding as appropriate.
        """
        value = Font(qtfont_class().to_py('10.5pt Test'))
        assert value.family() == 'Test'
        assert value.pointSize() >= 10
        assert value.pointSize() <= 11

    @pytest.mark.parametrize('val', [
        pytest.param('green "Foobar Neue"', marks=font_xfail),
        pytest.param('italic green "Foobar Neue"', marks=font_xfail),
        pytest.param('bold bold "Foobar Neue"', marks=font_xfail),
        pytest.param('bold italic "Foobar Neue"', marks=font_xfail),
        pytest.param('10pt 20px "Foobar Neue"', marks=font_xfail),
        pytest.param('bold', marks=font_xfail),
        pytest.param('italic', marks=font_xfail),
        pytest.param('green', marks=font_xfail),
        pytest.param('10pt', marks=font_xfail),
        pytest.param('10pt ""', marks=font_xfail),
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    def test_defaults_replacement(self, klass, monkeypatch):
        configtypes.FontBase.set_defaults(['Terminus'], '23pt')
        if klass is configtypes.Font:
            expected = '23pt Terminus'
        elif klass is configtypes.QtFont:
            desc = FontDesc(QFont.StyleNormal, QFont.Normal, 23, None,
                            'Terminus')
            expected = Font.fromdesc(desc)
        assert klass().to_py('23pt default_family') == expected


class TestFontFamily:

    TESTS = ['"Foobar Neue"', 'inconsolatazi4', 'Foobar']
    INVALID = [
        '10pt "Foobar Neue"',
        '10PT "Foobar Neue"',
        '10px "Foobar Neue"',
        '10PX "Foobar Neue"',
        'bold "Foobar Neue"',
        'italic "Foobar Neue"',
        'oblique "Foobar Neue"',
        'normal bold "Foobar Neue"',
        'bold italic "Foobar Neue"',
        'bold 10pt "Foobar Neue"',
        'italic 10pt "Foobar Neue"',
        'oblique 10pt "Foobar Neue"',
        'normal bold 10pt "Foobar Neue"',
        'bold italic 10pt "Foobar Neue"',
    ]

    @pytest.fixture
    def klass(self):
        return configtypes.FontFamily

    @pytest.mark.parametrize('val', TESTS)
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    @pytest.mark.parametrize('val', INVALID)
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


class TestRegex:

    @pytest.fixture
    def klass(self):
        return configtypes.Regex

    @pytest.mark.parametrize('val', [
        r'(foo|bar)?baz[fis]h',
        re.compile('foobar'),
    ])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == RegexEq(val)

    @pytest.mark.parametrize('val', [
        pytest.param(r'(foo|bar))?baz[fis]h', id='unmatched parens'),
        pytest.param('(' * 500, id='too many parens'),
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    @pytest.mark.parametrize('val', [
        r'foo\Xbar',
        r'foo\Cbar',
    ])
    def test_to_py_maybe_valid(self, klass, val):
        """Those values are valid on some Python versions (and systems?).

        On others, they raise a DeprecationWarning because of an invalid
        escape. This tests makes sure this gets translated to a
        ValidationError.
        """
        try:
            klass().to_py(val)
        except configexc.ValidationError:
            pass

    @pytest.mark.parametrize('warning', [
        Warning('foo'), DeprecationWarning('foo'),
    ])
    def test_passed_warnings(self, mocker, klass, warning):
        """Simulate re.compile showing a warning we don't know about yet.

        The warning should be passed.
        """
        regex = klass()
        m = mocker.patch('qutebrowser.config.configtypes.re')
        m.compile.side_effect = lambda *args: warnings.warn(warning)
        m.error = re.error
        with pytest.raises(type(warning)):
            regex.to_py('foo')

    def test_bad_pattern_warning(self, mocker, klass):
        """Test a simulated bad pattern warning.

        This only seems to happen with Python 3.5, so we simulate this for
        better coverage.
        """
        regex = klass()
        m = mocker.patch('qutebrowser.config.configtypes.re')
        m.compile.side_effect = lambda *args: warnings.warn(r'bad escape \C',
                                                            DeprecationWarning)
        m.error = re.error
        with pytest.raises(configexc.ValidationError):
            regex.to_py('foo')

    @pytest.mark.parametrize('flags, expected', [
        (None, 0),
        ('IGNORECASE', re.IGNORECASE),
        ('IGNORECASE | VERBOSE', re.IGNORECASE | re.VERBOSE),
    ])
    def test_flag_parsing(self, klass, flags, expected):
        typ = klass(flags=flags)
        assert typ.flags == expected

    @pytest.mark.parametrize('value', [r'foobar', re.compile(r'foobar')])
    def test_to_str(self, klass, value):
        assert klass().to_str(value) == 'foobar'


class TestDict:

    @pytest.fixture
    def klass(self):
        return configtypes.Dict

    @pytest.mark.parametrize('val', [
        '{"foo": "bar"}',
        '{"foo": "bar", "baz": "fish"}',
        '{}',
    ])
    def test_from_str_valid(self, klass, val):
        d = klass(keytype=configtypes.String(), valtype=configtypes.String(),
                  none_ok=True)
        assert d.from_str(val) == json.loads(val)

    @pytest.mark.parametrize('val', [
        '["foo"]',  # valid yaml but not a dict
        '{"hello": 23}',  # non-string as value
        '[invalid',  # invalid yaml
        '{}',  # Special case for none_ok=False
    ])
    def test_from_str_invalid(self, klass, val):
        d = klass(keytype=configtypes.String(), valtype=configtypes.String())
        with pytest.raises(configexc.ValidationError):
            d.from_str(val)

    def test_from_str_int(self):
        typ = configtypes.Dict(keytype=configtypes.String(),
                               valtype=configtypes.Int())
        assert typ.from_str('{"answer": 42}') == {"answer": 42}

    @pytest.mark.parametrize('obj, expected', [
        ({'a': 'b'}, {'a': 'b'}),
        ({}, {}),
        (None, {}),
    ])
    def test_from_obj(self, klass, obj, expected):
        d = klass(keytype=configtypes.String(), valtype=configtypes.String(),
                  none_ok=True)
        assert d.from_obj(obj) == expected

    @pytest.mark.parametrize('keytype, valtype, val', [
        (configtypes.String(), configtypes.String(), {'hello': 'world'}),
        (configtypes.String(), configtypes.Int(), {'hello': 42}),
    ])
    def test_to_py_valid(self, klass, keytype, valtype, val):
        assert klass(keytype=keytype, valtype=valtype).to_py(val) == val

    @pytest.mark.parametrize('val', [
        {'\U00010000': 'foo'},  # UTF-16 surrogate in key
        {'foo': '\U00010000'},  # UTF-16 surrogate in value
        {0: 'foo'},  # Invalid key type
        {'foo': 0},  # Invalid value type
    ])
    def test_to_py_invalid(self, klass, val):
        typ = klass(keytype=configtypes.String(), valtype=configtypes.String())
        with pytest.raises(configexc.ValidationError):
            typ.to_py(val)

    @pytest.mark.parametrize('kind, val, ok', [
        ('fixed', {"one": "1"}, True),  # missing key (gets filled with None)
        ('fixed', {"one": "1", "two": "2", "three": "3"}, False),  # extra key
        ('fixed', {"one": "1", "two": "2"}, True),

        ('required', {"one": "1"}, False),  # missing key
        ('required', {"one": "1", "two": "2", "three": "3"}, True),  # extra
        ('required', {"one": "1", "two": "2"}, True),
    ])
    @pytest.mark.parametrize('from_str', [True, False])
    def test_keys(self, klass, kind, val, ok, from_str):
        if kind == 'fixed':
            d = klass(keytype=configtypes.String(),
                      valtype=configtypes.String(none_ok=True),
                      fixed_keys=['one', 'two'])
            message = 'Expected keys .*'
        elif kind == 'required':
            d = klass(keytype=configtypes.String(),
                      valtype=configtypes.String(),
                      required_keys=['one', 'two'])
            message = 'Required keys .*'

        if ok:
            expectation = testutils.nop_contextmanager()
        else:
            expectation = pytest.raises(configexc.ValidationError,
                                        match=message)

        with expectation:
            if from_str:
                d.from_str(json.dumps(val))
            else:
                d.to_py(val)

    @hypothesis.given(val=strategies.dictionaries(
        strategies.text(min_size=1, alphabet=strategies.characters(
            # No control characters, surrogates, or codepoints encoded as
            # surrogate
            blacklist_categories=['Cc', 'Cs'], max_codepoint=0xFFFF)),
        strategies.booleans()))
    def test_hypothesis(self, klass, val):
        d = klass(keytype=configtypes.String(),
                  valtype=configtypes.Bool(),
                  none_ok=True)
        converted = d.to_py(val)
        expected = converted if converted else None
        assert d.from_str(d.to_str(converted)) == expected

    @hypothesis.given(val=strategies.dictionaries(strategies.text(min_size=1),
                                                  strategies.booleans()))
    def test_hypothesis_text(self, klass, val):
        text = json.dumps(val)
        d = klass(keytype=configtypes.String(), valtype=configtypes.Bool())
        try:
            converted = d.from_str(text)
        except configexc.ValidationError:
            return

        if len(converted) > 1:
            # For longer dicts, the key order could be switched
            return

        assert d.to_str(converted) == '' if not val else text

    @pytest.mark.parametrize('valtype, val, expected', [
        # simple dict
        (configtypes.String(), {'foo': 'bar'},
         '\n\n- +pass:[foo]+: +pass:[bar]+'),
        # dict as value
        (configtypes.Dict(keytype=configtypes.String(),
                          valtype=configtypes.String()),
         {'foo': {'bar': 'baz'}},
         '\n\n- +pass:[foo]+:\n\n* +pass:[bar]+: +pass:[baz]+'),
        # empty
        (configtypes.String(), {}, 'empty'),
    ])
    def test_to_doc(self, klass, valtype, val, expected):
        typ = klass(keytype=configtypes.String(), valtype=valtype)
        doc = typ.to_doc(val)
        print(doc)
        assert doc == expected

    def test_from_obj_sub(self):
        """Make sure the dict calls from_obj() on sub-types."""
        typ = configtypes.Dict(keytype=configtypes.String(),
                               valtype=FromObjType())
        value = typ.from_obj({'1': '2'})
        assert value == {'1': 2}

    def test_to_str(self, klass):
        typ = klass(keytype=configtypes.String(), valtype=configtypes.String())
        d = {'a': 'b', 'c': 'd'}
        assert typ.to_str(d) == '{"a": "b", "c": "d"}'


def unrequired_class(**kwargs):
    return configtypes.File(required=False, **kwargs)


@pytest.mark.usefixtures('config_tmpdir')
class TestFile:

    @pytest.fixture(params=[configtypes.File, unrequired_class])
    def klass(self, request):
        return request.param

    @pytest.fixture
    def file_class(self):
        return configtypes.File

    def test_to_py_does_not_exist_file(self, os_mock):
        """Test to_py with a file which does not exist (File)."""
        os_mock.path.isfile.return_value = False
        with pytest.raises(configexc.ValidationError):
            configtypes.File().to_py('foobar')

    def test_to_py_does_not_exist_optional_file(self, os_mock):
        """Test to_py with a file which does not exist (File)."""
        os_mock.path.isfile.return_value = False
        assert unrequired_class().to_py('foobar') == 'foobar'

    @pytest.mark.parametrize('val, expected', [
        ('/foobar', '/foobar'),
        ('~/foobar', '/home/foo/foobar'),
        ('$HOME/foobar', '/home/foo/foobar'),
    ])
    def test_to_py_exists_abs(self, klass, os_mock, val, expected):
        """Test to_py with a file which does exist."""
        os_mock.path.isfile.return_value = True
        assert klass().to_py(val) == expected

    def test_to_py_exists_rel(self, klass, os_mock, monkeypatch):
        """Test to_py with a relative path to an existing file."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config',
            lambda: '/home/foo/.config')
        os_mock.path.isfile.return_value = True
        os_mock.path.isabs.return_value = False
        assert klass().to_py('foobar') == '/home/foo/.config/foobar'
        os_mock.path.join.assert_called_once_with(
            '/home/foo/.config', 'foobar')

    def test_to_py_expanduser(self, klass, os_mock):
        """Test if to_py expands the user correctly."""
        os_mock.path.isfile.side_effect = (lambda path:
                                           path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        assert klass().to_py('~/foobar') == '/home/foo/foobar'

    def test_to_py_expandvars(self, klass, os_mock):
        """Test if to_py expands the environment vars correctly."""
        os_mock.path.isfile.side_effect = (lambda path:
                                           path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        assert klass().to_py('$HOME/foobar') == '/home/foo/foobar'

    def test_to_py_invalid_encoding(self, klass, os_mock, unicode_encode_err):
        """Test to_py with an invalid encoding, e.g. LC_ALL=C."""
        os_mock.path.isfile.side_effect = unicode_encode_err
        os_mock.path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            klass().to_py('foobar')


class TestDirectory:

    @pytest.fixture
    def klass(self):
        return configtypes.Directory

    def test_to_py_does_not_exist(self, klass, os_mock):
        """Test to_py with a directory which does not exist."""
        os_mock.path.isdir.return_value = False
        with pytest.raises(configexc.ValidationError):
            klass().to_py('foobar')

    def test_to_py_exists_abs(self, klass, os_mock):
        """Test to_py with a directory which does exist."""
        os_mock.path.isdir.return_value = True
        os_mock.path.isabs.return_value = True
        assert klass().to_py('foobar') == 'foobar'

    def test_to_py_exists_not_abs(self, klass, os_mock):
        """Test to_py with a dir which does exist but is not absolute."""
        os_mock.path.isdir.return_value = True
        os_mock.path.isabs.return_value = False
        with pytest.raises(configexc.ValidationError):
            klass().to_py('foobar')

    def test_to_py_expanduser(self, klass, os_mock):
        """Test if to_py expands the user correctly."""
        os_mock.path.isdir.side_effect = (lambda path:
                                          path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        assert klass().to_py('~/foobar') == '/home/foo/foobar'
        os_mock.path.expanduser.assert_called_once_with('~/foobar')

    def test_to_py_expandvars(self, klass, os_mock, monkeypatch):
        """Test if to_py expands the user correctly."""
        os_mock.path.isdir.side_effect = (lambda path:
                                          path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        assert klass().to_py('$HOME/foobar') == '/home/foo/foobar'
        os_mock.path.expandvars.assert_called_once_with('$HOME/foobar')

    def test_to_py_invalid_encoding(self, klass, os_mock,
                                    unicode_encode_err):
        """Test to_py with an invalid encoding, e.g. LC_ALL=C."""
        os_mock.path.isdir.side_effect = unicode_encode_err
        os_mock.path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            klass().to_py('foobar')


class TestFormatString:

    @pytest.fixture
    def klass(self):
        return configtypes.FormatString

    @pytest.fixture
    def typ(self, klass):
        return klass(fields=('foo', 'bar'))

    @pytest.mark.parametrize('val', [
        'foo bar baz',
        '{foo} {bar} baz',
    ])
    def test_to_py_valid(self, typ, val):
        assert typ.to_py(val) == val

    @pytest.mark.parametrize('val', [
        '{foo} {bar} {baz}',
        '{foo} {bar',
        '{1}',
    ])
    def test_to_py_invalid(self, typ, val):
        with pytest.raises(configexc.ValidationError):
            typ.to_py(val)

    @pytest.mark.parametrize('value', [
        None,
        ['one', 'two'],
        [('1', 'one'), ('2', 'two')],
    ])
    def test_complete(self, klass, value):
        assert klass(fields=('foo'), completions=value).complete() == value


class TestShellCommand:

    @pytest.fixture
    def klass(self):
        return configtypes.ShellCommand

    @pytest.mark.parametrize('kwargs, val, expected', [
        ({}, '[foobar]', ['foobar']),
        ({'placeholder': True}, '[foo, "{}", bar]', ['foo', '{}', 'bar']),
        ({'placeholder': True}, '["foo{}bar"]', ['foo{}bar']),
        ({'placeholder': True}, '[foo, "bar {}"]', ['foo', 'bar {}']),
        ({'placeholder': True}, '[f, "{file}", b]', ['f', '{file}', 'b']),
        ({'placeholder': True}, '["f{file}b"]', ['f{file}b']),
        ({'placeholder': True}, '[f, "b {file}"]', ['f', 'b {file}']),
    ])
    def test_valid(self, klass, kwargs, val, expected):
        cmd = klass(**kwargs)
        assert cmd.from_str(val) == expected
        assert cmd.to_py(expected) == expected

    @pytest.mark.parametrize('kwargs, val', [
        ({'placeholder': True}, '[foo, bar]'),
        ({'placeholder': True}, '[foo, "{", "}", bar'),
        ({'placeholder': True}, '[foo, bar]'),
        ({'placeholder': True}, '[foo, "{fi", "le}", bar'),

        # Like valid ones but with wrong placeholder
        ({'placeholder': True}, '[f, "{wrong}", b]'),
        ({'placeholder': True}, '["f{wrong}b"]'),
        ({'placeholder': True}, '[f, "b {wrong}"]'),
    ])
    def test_from_str_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).from_str(val)


class TestProxy:

    @pytest.fixture
    def klass(self):
        return configtypes.Proxy

    @pytest.mark.parametrize('val, expected', [
        ('system', configtypes.SYSTEM_PROXY),
        ('none', QNetworkProxy(QNetworkProxy.NoProxy)),
        ('socks://example.com/',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')),
        ('socks5://foo:bar@example.com:2323',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2323,
                       'foo', 'bar')),
        ('pac+http://example.com/proxy.pac',
         pac.PACFetcher(QUrl('pac+http://example.com/proxy.pac'))),
        ('pac+file:///tmp/proxy.pac',
         pac.PACFetcher(QUrl('pac+file:///tmp/proxy.pac'))),
    ])
    def test_to_py_valid(self, klass, val, expected):
        actual = klass().to_py(val)
        if isinstance(actual, QNetworkProxy):
            actual = QNetworkProxy(actual)
        assert actual == expected

    @pytest.mark.parametrize('val', [
        'blah',
        ':',  # invalid URL
        'ftp://example.com/',  # invalid scheme
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    def test_complete(self, klass):
        """Test complete."""
        actual = klass().complete()
        expected = [('system', "Use the system wide proxy."),
                    ('none', "Don't use any proxy"),
                    ('http://', 'HTTP proxy URL')]
        assert actual[:3] == expected


class TestSearchEngineUrl:

    @pytest.fixture
    def klass(self):
        return configtypes.SearchEngineUrl

    @pytest.mark.parametrize('val', [
        'http://example.com/?q={}',
        'http://example.com/?q={0}',
        'http://example.com/?q={0}&a={0}',
    ])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    @pytest.mark.parametrize('val', [
        'foo',  # no placeholder
        'foo{bar}baz{}',  # {bar} format string variable
        '{1}{}',  # numbered format string variable
        '{{}',  # invalid format syntax
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


class TestFuzzyUrl:

    @pytest.fixture
    def klass(self):
        return configtypes.FuzzyUrl

    @pytest.mark.parametrize('val, expected', [
        ('http://example.com/?q={}', QUrl('http://example.com/?q={}')),
        ('example.com', QUrl('http://example.com')),
    ])
    def test_to_py_valid(self, klass, val, expected):
        assert klass().to_py(val) == expected

    @pytest.mark.parametrize('val', [
        '::foo',  # invalid URL
        'foo bar',  # invalid search term
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


class TestPadding:

    @pytest.fixture
    def klass(self):
        return configtypes.Padding

    def test_to_py_valid(self, klass):
        val = {'top': 1, 'bottom': 2, 'left': 3, 'right': 4}
        expected = configtypes.PaddingValues(1, 2, 3, 4)
        assert klass().to_py(val) == expected

    @pytest.mark.parametrize('val', [
        {'top': 1, 'bottom': 2, 'left': 3, 'right': 4, 'foo': 5},
        {'top': 1, 'bottom': 2, 'left': 3, 'right': 'four'},
        {'top': 1, 'bottom': 2},
        {'top': -1, 'bottom': 2, 'left': 3, 'right': 4},
        {'top': 0.1, 'bottom': 2, 'left': 3, 'right': 4},
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


class TestEncoding:

    @pytest.fixture
    def klass(self):
        return configtypes.Encoding

    @pytest.mark.parametrize('val', ['utf-8', 'UTF-8', 'iso8859-1'])
    def test_to_py_valid(self, klass, val):
        assert klass().to_py(val) == val

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py('blubber')


class TestUrl:

    TESTS = {
        'http://qutebrowser.org/': QUrl('http://qutebrowser.org/'),
        'http://heise.de/': QUrl('http://heise.de/'),
    }

    @pytest.fixture
    def klass(self):
        return configtypes.Url

    @pytest.mark.parametrize('val, expected', list(TESTS.items()))
    def test_to_py_valid(self, klass, val, expected):
        assert klass().to_py(val) == expected

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py('+')


class TestSessionName:

    @pytest.fixture
    def klass(self):
        return configtypes.SessionName

    def test_to_py_valid(self, klass):
        assert klass().to_py('foobar') == 'foobar'

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py('_foo')


class TestConfirmQuit:

    TESTS = [
        ['multiple-tabs', 'downloads'],
        ['downloads', 'multiple-tabs'],
        ['downloads', None, 'multiple-tabs'],
    ]

    @pytest.fixture
    def klass(self):
        return configtypes.ConfirmQuit

    @pytest.mark.parametrize('val', TESTS)
    def test_to_py_valid(self, klass, val):
        cq = klass(none_ok=True)
        assert cq.to_py(val) == val
        assert cq.from_str(json.dumps(val)) == val

    @pytest.mark.parametrize('val', [
        ['foo'],
        ['downloads', 'foo'],  # valid value mixed with invalid one
        ['downloads', 'multiple-tabs', 'downloads'],  # duplicate value
        ['always', 'downloads'],  # always combined
        ['never', 'downloads'],  # never combined
    ])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)


class TestKey:

    @pytest.fixture
    def klass(self):
        return configtypes.Key

    @pytest.mark.parametrize('val, expected', [
        ('gC', keyutils.KeySequence.parse('gC')),
        ('<Control-x>', keyutils.KeySequence.parse('<ctrl+x>')),
        ('<alt-1>', keyutils.KeySequence.parse('<alt+1>')),
        ('0', keyutils.KeySequence.parse('0')),
        ('1', keyutils.KeySequence.parse('1')),
        ('a1', keyutils.KeySequence.parse('a1')),
    ])
    def test_to_py_valid(self, klass, val, expected):
        assert klass().to_py(val) == expected

    @pytest.mark.parametrize('val', ['\U00010000', '<blub>'])
    def test_to_py_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().to_py(val)

    def test_normalized(self, klass):
        assert klass().from_obj('<ctrl-q>') == '<Ctrl+q>'


class TestUrlPattern:

    @pytest.fixture
    def klass(self):
        return configtypes.UrlPattern

    def test_to_py_valid(self, klass):
        pattern = 'http://*.example.com/'
        assert klass().to_py(pattern) == urlmatch.UrlPattern(pattern)

    def test_to_py_invalid(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().to_py('http://')


@pytest.mark.parametrize('first, second, equal', [
    (re.compile('foo'), RegexEq('foo'), True),
    (RegexEq('bar'), re.compile('bar'), True),
    (RegexEq('qwer'), RegexEq('qwer'), True),
    (re.compile('qux'), RegexEq('foo'), False),
    (RegexEq('spam'), re.compile('eggs'), False),
    (RegexEq('qwer'), RegexEq('rewq'), False),

    (re.compile('foo', re.I), RegexEq('foo', re.I), True),
    (RegexEq('bar', re.M), re.compile('bar', re.M), True),
    (re.compile('qux', re.M), RegexEq('qux', re.I), False),
    (RegexEq('spam', re.S), re.compile('eggs', re.S), False),

    (re.compile('(?i)foo'), RegexEq('(?i)foo'), True),
    (re.compile('(?i)bar'), RegexEq('bar'), False),
])
def test_regex_eq(first, second, equal):
    if equal:
        # Assert that the check is commutative
        assert first == second
        assert second == first
    else:
        assert first != second
        assert second != first
