# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import collections
import itertools
import os.path
import base64
import warnings

import pytest
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtNetwork import QNetworkProxy

from qutebrowser.config import configtypes, configexc
from qutebrowser.utils import debug, utils


class Font(QFont):

    """A QFont with a nicer repr()."""

    def __repr__(self):
        weight = debug.qenum_key(QFont, self.weight(), add_base=True,
                                 klass=QFont.Weight)
        return utils.get_repr(self, family=self.family(), pt=self.pointSize(),
                              px=self.pixelSize(), weight=weight,
                              style=self.style())

    @classmethod
    def fromdesc(cls, desc):
        """Get a Font based on a font description."""
        style, weight, ptsize, pxsize, family = desc
        f = cls()
        f.setStyle(style)
        f.setWeight(weight)
        if ptsize is not None and ptsize != -1:
            f.setPointSize(ptsize)
        if pxsize is not None and ptsize != -1:
            f.setPixelSize(pxsize)
        f.setFamily(family)
        return f


class NetworkProxy(QNetworkProxy):

    """A QNetworkProxy with a nicer repr()."""

    def __repr__(self):
        return utils.get_repr(self, type=self.type(), hostName=self.hostName(),
                              port=self.port(), user=self.user(),
                              password=self.password())


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

    """Test ValidValues."""

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


class TestBaseType:

    """Test BaseType."""

    @pytest.fixture
    def basetype(self):
        return configtypes.BaseType()

    @pytest.mark.parametrize('val, expected', [
        ('foobar', 'foobar'),
        ('', None),
    ])
    def test_transform(self, basetype, val, expected):
        """Test transform with a value."""
        assert basetype.transform(val) == expected

    def test_validate_not_implemented(self, basetype):
        """Test validate without valid_values set."""
        with pytest.raises(NotImplementedError):
            basetype.validate("foo")

    def test_validate(self, basetype):
        """Test validate with valid_values set."""
        basetype.valid_values = configtypes.ValidValues('foo', 'bar')
        basetype.validate('bar')
        with pytest.raises(configexc.ValidationError):
            basetype.validate('baz')

    @pytest.mark.parametrize('val', ['', 'foobar', 'snowman: ☃', 'foo bar'])
    def test_basic_validation_valid(self, basetype, val):
        """Test _basic_validation with valid values."""
        basetype.none_ok = True
        basetype._basic_validation(val)

    @pytest.mark.parametrize('val', ['', '\x00'])
    def test_basic_validation_invalid(self, basetype, val):
        """Test _basic_validation with invalid values."""
        with pytest.raises(configexc.ValidationError):
            basetype._basic_validation(val)

    def test_complete_none(self, basetype):
        """Test complete with valid_values not set."""
        assert basetype.complete() is None

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
    def test_complete_without_desc(self, basetype, valid_values, completions):
        """Test complete with valid_values set without description."""
        basetype.valid_values = configtypes.ValidValues(*valid_values)
        assert basetype.complete() == completions


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

    """Test MappingType."""

    TESTS = {
        '': None,
        'one': 1,
        'two': 2,
        'ONE': 1,
    }

    @pytest.fixture
    def klass(self):
        return MappingSubclass

    @pytest.mark.parametrize('val', sorted(TESTS.keys()))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', 'one!', 'blah'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected

    @pytest.mark.parametrize('typ', [configtypes.ColorSystem(),
                                     configtypes.Position(),
                                     configtypes.SelectOnRemove()])
    def test_mapping_type_matches_valid_values(self, typ):
        assert list(sorted(typ.MAPPING)) == list(sorted(typ.valid_values))


class TestString:

    """Test String."""

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
        ({'none_ok': True}, ''),  # Empty with none_ok
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
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, ''),  # Empty without none_ok
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
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    def test_validate_duplicate_invalid(self):
        typ = configtypes.UniqueCharString()
        with pytest.raises(configexc.ValidationError):
            typ.validate('foobar')

    def test_transform(self, klass):
        assert klass().transform('fobar') == 'fobar'

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


class TestList:

    """Test List."""

    @pytest.fixture
    def klass(self):
        return configtypes.List

    @pytest.mark.parametrize('val',
        ['', 'foo', 'foo,bar', 'foo, bar'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', 'foo,,bar'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_invalid_empty_value_none_ok(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass(none_ok=True).validate('foo,,bar')

    @pytest.mark.parametrize('val, expected', [
        ('foo', ['foo']),
        ('foo,bar,baz', ['foo', 'bar', 'baz']),
        ('', None),
        # Not implemented yet
        pytest.mark.xfail(('foo, bar', ['foo', 'bar'])),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class FlagListSubclass(configtypes.FlagList):

    """A subclass of FlagList which we use in tests.

    Valid values are 'foo', 'bar' and 'baz'.
    """

    combinable_values = ['foo', 'bar']

    def __init__(self, none_ok=False):
        super().__init__(none_ok)
        self.valid_values = configtypes.ValidValues('foo', 'bar', 'baz')


class TestFlagList:

    """Test FlagList."""

    @pytest.fixture
    def klass(self):
        return FlagListSubclass

    @pytest.fixture
    def klass_valid_none(self):
        """Return a FlagList with valid_values = None."""
        return configtypes.FlagList

    @pytest.mark.parametrize('val', ['', 'foo', 'foo,bar', 'foo,'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['qux', 'foo,qux', 'foo,foo'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', 'foo,', 'foo,,bar'])
    def test_validate_empty_value_not_okay(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass(none_ok=False).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('foo', ['foo']),
        ('foo,bar', ['foo', 'bar']),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected

    @pytest.mark.parametrize('val', ['spam', 'spam,eggs'])
    def test_validate_values_none(self, klass_valid_none, val):
        klass_valid_none().validate(val)

    def test_complete(self, klass):
        """Test completing by doing some samples."""
        completions = [e[0] for e in klass().complete()]
        assert 'foo' in completions
        assert 'bar' in completions
        assert 'baz' in completions
        assert 'foo,bar' in completions
        for val in completions:
            assert 'baz,' not in val
            assert ',baz' not in val

    def test_complete_all_valid_values(self, klass):
        inst = klass()
        inst.combinable_values = None
        completions = [e[0] for e in inst.complete()]
        assert 'foo' in completions
        assert 'bar' in completions
        assert 'baz' in completions
        assert 'foo,bar' in completions
        assert 'foo,baz' in completions

    def test_complete_no_valid_values(self, klass_valid_none):
        assert klass_valid_none().complete() is None


class TestBool:

    """Test Bool."""

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

        '': None,
    }

    INVALID = ['10', 'yess', 'false_', '']

    @pytest.fixture
    def klass(self):
        return configtypes.Bool

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)


class TestBoolAsk:

    """Test BoolAsk."""

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
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)


class TestInt:

    """Test Int."""

    @pytest.fixture
    def klass(self):
        return configtypes.Int

    def test_minval_gt_maxval(self, klass):
        with pytest.raises(ValueError):
            klass(minval=2, maxval=1)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337'),
        ({}, '0'),
        ({'none_ok': True}, ''),
        ({'minval': 2}, '2'),
        ({'maxval': 2}, '2'),
        ({'minval': 2, 'maxval': 3}, '2'),
        ({'minval': 2, 'maxval': 3}, '3'),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, ''),
        ({}, '2.5'),
        ({}, 'foobar'),
        ({'minval': 2}, '1'),
        ({'maxval': 2}, '3'),
        ({'minval': 2, 'maxval': 3}, '1'),
        ({'minval': 2, 'maxval': 3}, '4'),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [('1', 1), ('1337', 1337),
                                               ('', None)])
    def test_transform(self, klass, val, expected):
        assert klass(none_ok=True).transform(val) == expected


class TestIntList:

    """Test IntList."""

    @pytest.fixture
    def klass(self):
        return configtypes.IntList

    @pytest.mark.parametrize('val', ['', '1,2', '1', '23,1337'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', '1,,2', '23,foo,1337'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_invalid_empty_value_none_ok(self, klass):
        klass(none_ok=True).validate('1,,2')

    @pytest.mark.parametrize('val, expected', [
        ('1', [1]),
        ('23,42', [23, 42]),
        ('', None),
        ('1,,2', [1, None, 2]),
        ('23, 42', [23, 42]),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestFloat:

    """Test Float."""

    @pytest.fixture
    def klass(self):
        return configtypes.Float

    def test_minval_gt_maxval(self, klass):
        with pytest.raises(ValueError):
            klass(minval=2, maxval=1)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337.42'),
        ({}, '0'),
        ({}, '1337'),
        ({'none_ok': True}, ''),
        ({'minval': 2}, '2.00'),
        ({'maxval': 2}, '2.00'),
        ({'minval': 2, 'maxval': 3}, '2.00'),
        ({'minval': 2, 'maxval': 3}, '3.00'),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, ''),
        ({}, '2.5.2'),
        ({}, 'foobar'),
        ({'minval': 2}, '1.99'),
        ({'maxval': 2}, '2.01'),
        ({'minval': 2, 'maxval': 3}, '1.99'),
        ({'minval': 2, 'maxval': 3}, '3.01'),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('1337', 1337.00),
        ('1337.42', 1337.42),
        ('', None),
    ])
    def test_transform(self, klass, val, expected):
        assert klass(none_ok=True).transform(val) == expected


class TestPerc:

    """Test Perc."""

    @pytest.fixture
    def klass(self):
        return configtypes.Perc

    def test_minval_gt_maxval(self, klass):
        with pytest.raises(ValueError):
            klass(minval=2, maxval=1)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337%'),
        ({'minval': 2}, '2%'),
        ({'maxval': 2}, '2%'),
        ({'minval': 2, 'maxval': 3}, '2%'),
        ({'minval': 2, 'maxval': 3}, '3%'),
        ({'none_ok': True}, ''),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337'),
        ({}, '1337%%'),
        ({}, 'foobar'),
        ({}, ''),
        ({'minval': 2}, '1%'),
        ({'maxval': 2}, '3%'),
        ({'minval': 2, 'maxval': 3}, '1%'),
        ({'minval': 2, 'maxval': 3}, '4%'),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('1337%', 1337),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestPercList:

    """Test PercList."""

    @pytest.fixture
    def klass(self):
        return configtypes.PercList

    def test_minval_gt_maxval(self, klass):
        with pytest.raises(ValueError):
            klass(minval=2, maxval=1)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '23%,42%,1337%'),
        ({'minval': 2}, '2%,3%'),
        ({'maxval': 2}, '1%,2%'),
        ({'minval': 2, 'maxval': 3}, '2%,3%'),
        ({'none_ok': True}, '42%,,23%'),
        ({'none_ok': True}, ''),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '23%,42,1337%'),
        ({'minval': 2}, '1%,2%'),
        ({'maxval': 2}, '2%,3%'),
        ({'minval': 2, 'maxval': 3}, '1%,2%'),
        ({'minval': 2, 'maxval': 3}, '3%,4%'),
        ({}, '42%,,23%'),
        ({}, ''),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('1337%', [1337]),
        ('23%,42%,1337%', [23, 42, 1337]),
        ('23%,,42%', [23, None, 42]),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestPercOrInt:

    """Test PercOrInt."""

    @pytest.fixture
    def klass(self):
        return configtypes.PercOrInt

    def test_minint_gt_maxint(self, klass):
        with pytest.raises(ValueError):
            klass(minint=2, maxint=1)

    def test_minperc_gt_maxperc(self, klass):
        with pytest.raises(ValueError):
            klass(minperc=2, maxperc=1)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337%'),
        ({}, '1337'),
        ({'none_ok': True}, ''),

        ({'minperc': 2}, '2%'),
        ({'maxperc': 2}, '2%'),
        ({'minperc': 2, 'maxperc': 3}, '2%'),
        ({'minperc': 2, 'maxperc': 3}, '3%'),

        ({'minint': 2}, '2'),
        ({'maxint': 2}, '2'),
        ({'minint': 2, 'maxint': 3}, '2'),
        ({'minint': 2, 'maxint': 3}, '3'),

        ({'minperc': 2, 'maxperc': 3}, '1'),
        ({'minperc': 2, 'maxperc': 3}, '4'),
        ({'minint': 2, 'maxint': 3}, '1%'),
        ({'minint': 2, 'maxint': 3}, '4%'),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '1337%%'),
        ({}, 'foobar'),
        ({}, ''),

        ({'minperc': 2}, '1%'),
        ({'maxperc': 2}, '3%'),
        ({'minperc': 2, 'maxperc': 3}, '1%'),
        ({'minperc': 2, 'maxperc': 3}, '4%'),

        ({'minint': 2}, '1'),
        ({'maxint': 2}, '3'),
        ({'minint': 2, 'maxint': 3}, '1'),
        ({'minint': 2, 'maxint': 3}, '4'),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('1337%', '1337%'),
        ('1337', '1337'),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestCommand:

    """Test Command."""

    @pytest.fixture(autouse=True)
    def patch(self, monkeypatch, stubs):
        """Patch the cmdutils module to provide fake commands."""
        cmd_utils = stubs.FakeCmdUtils({
            'cmd1': stubs.FakeCommand(desc="desc 1"),
            'cmd2': stubs.FakeCommand(desc="desc 2")})
        monkeypatch.setattr('qutebrowser.config.configtypes.cmdutils',
                            cmd_utils)

    @pytest.fixture
    def klass(self):
        return configtypes.Command

    @pytest.mark.parametrize('val', ['', 'cmd1', 'cmd2', 'cmd1  foo bar',
                                     'cmd2  baz fish'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', 'cmd3', 'cmd3  foo bar', ' '])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [('foo bar', 'foo bar'),
                                               ('', None)])
    def test_transform(self, val, expected, klass):
        assert klass().transform(val) == expected

    def test_complete(self, klass):
        """Test completion."""
        items = klass().complete()
        assert len(items) == 2
        assert ('cmd1', "desc 1") in items
        assert ('cmd2', "desc 2") in items


class TestColorSystem:

    """Test ColorSystem."""

    TESTS = {
        'RGB': QColor.Rgb,
        'rgb': QColor.Rgb,
        'HSV': QColor.Hsv,
        'hsv': QColor.Hsv,
        'HSL': QColor.Hsl,
        'hsl': QColor.Hsl,
        'none': None,
        'None': None,
        '': None,
    }
    INVALID = ['RRGB', 'HSV ', '']  # '' is invalid with none_ok=False

    @pytest.fixture
    def klass(self):
        return configtypes.ColorSystem

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class ColorTests:

    """Generator for tests for TestColors."""

    TYPES = [configtypes.QtColor, configtypes.CssColor, configtypes.QssColor]

    TESTS = [
        ('#123', TYPES),
        ('#112233', TYPES),
        ('#111222333', TYPES),
        ('#111122223333', TYPES),
        ('red', TYPES),
        ('', TYPES),

        ('#00000G', []),
        ('#123456789ABCD', []),
        ('#12', []),
        ('foobar', []),
        ('42', []),
        ('rgb(1, 2, 3, 4)', []),
        ('foo(1, 2, 3)', []),

        ('rgb(0, 0, 0)', [configtypes.QssColor]),
        ('rgb(0,0,0)', [configtypes.QssColor]),
        ('-foobar(42)', [configtypes.CssColor]),

        ('rgba(255, 255, 255, 255)', [configtypes.QssColor]),
        ('rgba(255,255,255,255)', [configtypes.QssColor]),
        ('hsv(359, 255, 255)', [configtypes.QssColor]),
        ('hsva(359, 255, 255, 255)', [configtypes.QssColor]),
        ('hsv(10%, 10%, 10%)', [configtypes.QssColor]),
        ('hsv(10%,10%,10%)', [configtypes.QssColor]),
        ('qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 white, '
         'stop: 0.4 gray, stop:1 green)', [configtypes.QssColor]),
        ('qconicalgradient(cx:0.5, cy:0.5, angle:30, stop:0 white, '
         'stop:1 #00FF00)', [configtypes.QssColor]),
        ('qradialgradient(cx:0, cy:0, radius: 1, fx:0.5, fy:0.5, '
         'stop:0 white, stop:1 green)', [configtypes.QssColor]),
    ]

    COMBINATIONS = list(itertools.product(TESTS, TYPES))

    def __init__(self):
        self.valid = list(self._generate_valid())
        self.invalid = list(self._generate_invalid())

    def _generate_valid(self):
        for (val, valid_classes), klass in self.COMBINATIONS:
            if klass in valid_classes:
                yield klass, val

    def _generate_invalid(self):
        for (val, valid_classes), klass in self.COMBINATIONS:
            if klass not in valid_classes:
                yield klass, val


class TestColors:

    """Test QtColor/CssColor/QssColor."""

    TESTS = ColorTests()

    @pytest.fixture(params=ColorTests.TYPES)
    def klass_fixt(self, request):
        """Fixture which provides all ColorTests classes.

        Named klass_fix so it has a different name from the parametrized klass,
        see https://github.com/pytest-dev/pytest/issues/979.
        """
        return request.param

    def test_test_generator(self):
        """Some sanity checks for ColorTests."""
        assert self.TESTS.valid
        assert self.TESTS.invalid

    @pytest.mark.parametrize('klass, val', TESTS.valid)
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('klass, val', TESTS.invalid)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_validate_invalid_empty(self, klass_fixt):
        with pytest.raises(configexc.ValidationError):
            klass_fixt().validate('')

    @pytest.mark.parametrize('klass, val', TESTS.valid)
    def test_transform(self, klass, val):
        """Test transform of all color types."""
        if not val:
            expected = None
        elif klass is configtypes.QtColor:
            expected = QColor(val)
        else:
            expected = val
        assert klass().transform(val) == expected


FontDesc = collections.namedtuple('FontDesc',
                                  ['style', 'weight', 'pt', 'px', 'family'])


class TestFont:

    """Test Font/QtFont."""

    TESTS = {
        # (style, weight, pointsize, pixelsize, family
        '"Foobar Neue"':
            FontDesc(QFont.StyleNormal, QFont.Normal, -1, -1, 'Foobar Neue'),
        'inconsolatazi4':
            FontDesc(QFont.StyleNormal, QFont.Normal, -1, -1,
                     'inconsolatazi4'),
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
            FontDesc(QFont.StyleNormal, 37.5, 10, None, 'Foobar Neue'),
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

    @pytest.mark.parametrize('val', sorted(list(TESTS)) + [''])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        font_xfail('green "Foobar Neue"'),
        font_xfail('italic green "Foobar Neue"'),
        font_xfail('bold bold "Foobar Neue"'),
        font_xfail('bold italic "Foobar Neue"'),
        font_xfail('10pt 20px "Foobar Neue"'),
        font_xfail('bold'),
        font_xfail('italic'),
        font_xfail('green'),
        font_xfail('10pt'),
        font_xfail('10pt ""'),
        '%',
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_validate_invalid_none(self, klass):
        """Test validate with empty value and none_ok=False.

        Not contained in test_validate_invalid so it can be marked xfail.
        """
        with pytest.raises(configexc.ValidationError):
            klass().validate('')

    @pytest.mark.parametrize('string', sorted(TESTS))
    def test_transform_font(self, font_class, string):
        assert font_class().transform(string) == string

    @pytest.mark.parametrize('string, desc', sorted(TESTS.items()))
    def test_transform_qtfont(self, qtfont_class, string, desc):
        assert Font(qtfont_class().transform(string)) == Font.fromdesc(desc)

    def test_transform_qtfont_float(self, qtfont_class):
        """Test QtFont's transform with a float as point size.

        We can't test the point size for equality as Qt seems to do some
        rounding as appropriate.
        """
        value = Font(qtfont_class().transform('10.5pt "Foobar Neue"'))
        assert value.family() == 'Foobar Neue'
        assert value.weight() == QFont.Normal
        assert value.style() == QFont.StyleNormal
        assert value.pointSize() >= 10
        assert value.pointSize() <= 11

    def test_transform_empty(self, klass):
        assert klass().transform('') is None


class TestFontFamily:

    """Test FontFamily."""

    TESTS = ['"Foobar Neue"', 'inconsolatazi4', 'Foobar', '']
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
        '',  # with none_ok=False
        '%',
    ]

    @pytest.fixture
    def klass(self):
        return configtypes.FontFamily

    @pytest.mark.parametrize('val', TESTS)
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [('foobar', 'foobar'),
                                               ('', None)])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestRegex:

    """Test Regex."""

    @pytest.fixture
    def klass(self):
        return configtypes.Regex

    @pytest.mark.parametrize('val', [r'(foo|bar)?baz[fis]h', ''])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [r'(foo|bar))?baz[fis]h', '', '(' * 500],
                             ids=['unmatched parens', 'empty',
                                  'too many parens'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val', [
        r'foo\Xbar',
        r'foo\Cbar',
    ])
    def test_validate_maybe_valid(self, klass, val):
        """Those values are valid on some Python versions (and systems?).

        On others, they raise a DeprecationWarning because of an invalid
        escape. This tests makes sure this gets translated to a
        ValidationError.
        """
        try:
            klass().validate(val)
        except configexc.ValidationError:
            pass

    @pytest.mark.parametrize('val, expected', [
        (r'foobar', RegexEq(r'foobar')),
        ('', None),
    ])
    def test_transform_empty(self, klass, val, expected):
        assert klass().transform(val) == expected

    @pytest.mark.parametrize('warning', [
        Warning('foo'), DeprecationWarning('foo'),
    ])
    def test_passed_warnings(self, mocker, klass, warning):
        """Simulate re.compile showing a warning we don't know about yet.

        The warning should be passed.
        """
        m = mocker.patch('qutebrowser.config.configtypes.re')
        m.compile.side_effect = lambda *args: warnings.warn(warning)
        m.error = re.error
        with pytest.raises(type(warning)):
            klass().validate('foo')

    def test_bad_pattern_warning(self, mocker, klass):
        """Test a simulated bad pattern warning.

        This only seems to happen with Python 3.5, so we simulate this for
        better coverage.
        """
        m = mocker.patch('qutebrowser.config.configtypes.re')
        m.compile.side_effect = lambda *args: warnings.warn(r'bad escape \C',
                                                            DeprecationWarning)
        m.error = re.error
        with pytest.raises(configexc.ValidationError):
            klass().validate('foo')


class TestRegexList:

    """Test RegexList."""

    @pytest.fixture
    def klass(self):
        return configtypes.RegexList

    @pytest.mark.parametrize('val', [
        r'(foo|bar),[abcd]?,1337{42}',
        r'(foo|bar),,1337{42}',
        r'',
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        r'(foo|bar),,1337{42}',
        r'',
        r'(foo|bar),((),1337{42}',
        r'(' * 500,
    ], ids=['empty value', 'empty', 'unmatched parens', 'too many parens'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val', [
        r'foo\Xbar',
        r'foo\Cbar',
    ])
    def test_validate_maybe_valid(self, klass, val):
        """Those values are valid on some Python versions (and systems?).

        On others, they raise a DeprecationWarning because of an invalid
        escape. This tests makes sure this gets translated to a
        ValidationError.
        """
        try:
            klass().validate(val)
        except configexc.ValidationError:
            pass

    @pytest.mark.parametrize('val, expected', [
        ('foo', [RegexEq('foo')]),
        ('foo,bar,baz', [RegexEq('foo'), RegexEq('bar'),
                         RegexEq('baz')]),
        ('foo,,bar', [RegexEq('foo'), None, RegexEq('bar')]),
        ('', None),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


def unrequired_class(**kwargs):
    return configtypes.File(required=False, **kwargs)


@pytest.mark.usefixtures('qapp')
@pytest.mark.usefixtures('config_tmpdir')
class TestFileAndUserStyleSheet:

    """Test File/UserStyleSheet."""

    @pytest.fixture(params=[
        configtypes.File,
        configtypes.UserStyleSheet,
        unrequired_class,
    ])
    def klass(self, request):
        return request.param

    @pytest.fixture
    def file_class(self):
        return configtypes.File

    @pytest.fixture
    def userstylesheet_class(self):
        return configtypes.UserStyleSheet

    def _expected(self, klass, arg):
        """Get the expected value."""
        if not arg:
            return None
        elif klass is configtypes.File:
            return arg
        elif klass is configtypes.UserStyleSheet:
            return QUrl.fromLocalFile(arg)
        elif klass is unrequired_class:
            return arg
        else:
            assert False, klass

    def test_validate_empty(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().validate('')

    def test_validate_empty_none_ok(self, klass):
        klass(none_ok=True).validate('')

    def test_validate_does_not_exist_file(self, os_mock):
        """Test validate with a file which does not exist (File)."""
        os_mock.path.isfile.return_value = False
        with pytest.raises(configexc.ValidationError):
            configtypes.File().validate('foobar')

    def test_validate_does_not_exist_optional_file(self, os_mock):
        """Test validate with a file which does not exist (File)."""
        os_mock.path.isfile.return_value = False
        configtypes.File(required=False).validate('foobar')

    def test_validate_does_not_exist_userstylesheet(self, os_mock):
        """Test validate with a file which does not exist (UserStyleSheet)."""
        os_mock.path.isfile.return_value = False
        configtypes.UserStyleSheet().validate('foobar')

    def test_validate_exists_abs(self, klass, os_mock):
        """Test validate with a file which does exist."""
        os_mock.path.isfile.return_value = True
        os_mock.path.isabs.return_value = True
        klass().validate('foobar')

    def test_validate_exists_rel(self, klass, os_mock, monkeypatch):
        """Test validate with a relative path to an existing file."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config',
            lambda: '/home/foo/.config/')
        os_mock.path.isfile.return_value = True
        os_mock.path.isabs.return_value = False
        klass().validate('foobar')
        os_mock.path.join.assert_called_once_with(
            '/home/foo/.config/', 'foobar')

    def test_validate_rel_config_none_file(self, os_mock, monkeypatch):
        """Test with a relative path and standarddir.config returning None."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config', lambda: None)
        os_mock.path.isabs.return_value = False
        with pytest.raises(configexc.ValidationError):
            configtypes.File().validate('foobar')

    @pytest.mark.parametrize('configtype, value, raises', [
        (configtypes.File(), 'foobar', True),
        (configtypes.UserStyleSheet(), 'foobar', False),
        (configtypes.UserStyleSheet(), '\ud800', True),
        (configtypes.File(required=False), 'foobar', False),
    ], ids=['file-foobar', 'userstylesheet-foobar', 'userstylesheet-unicode',
            'file-optional-foobar'])
    def test_validate_rel_inexistent(self, os_mock, monkeypatch, configtype,
                                     value, raises):
        """Test with a relative path and standarddir.config returning None."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config',
            lambda: 'this/does/not/exist')
        os_mock.path.isabs.return_value = False
        os_mock.path.isfile.side_effect = os.path.isfile

        if raises:
            with pytest.raises(configexc.ValidationError):
                configtype.validate(value)
        else:
            configtype.validate(value)

    def test_validate_expanduser(self, klass, os_mock):
        """Test if validate expands the user correctly."""
        os_mock.path.isfile.side_effect = (lambda path:
                                           path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        klass().validate('~/foobar')

    def test_validate_expandvars(self, klass, os_mock):
        """Test if validate expands the environment vars correctly."""
        os_mock.path.isfile.side_effect = (lambda path:
                                           path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        klass().validate('$HOME/foobar')

    def test_validate_invalid_encoding(self, klass, os_mock,
                                       unicode_encode_err):
        """Test validate with an invalid encoding, e.g. LC_ALL=C."""
        os_mock.path.isfile.side_effect = unicode_encode_err
        os_mock.path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            klass().validate('foobar')

    @pytest.mark.parametrize('val, expected', [
        ('/foobar', '/foobar'),
        ('~/foobar', '/home/foo/foobar'),
        ('$HOME/foobar', '/home/foo/foobar'),
        ('', None),
    ])
    def test_transform_abs(self, klass, os_mock, val, expected):
        assert klass().transform(val) == self._expected(klass, expected)

    def test_transform_relative(self, klass, os_mock, monkeypatch):
        """Test transform() with relative dir and an available configdir."""
        os_mock.path.exists.return_value = True  # for TestUserStyleSheet
        os_mock.path.isabs.return_value = False
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config',
            lambda: '/configdir')
        expected = self._expected(klass, '/configdir/foo')
        assert klass().transform('foo') == expected

    @pytest.mark.parametrize('no_config', [False, True])
    def test_transform_userstylesheet_base64(self, monkeypatch, no_config):
        """Test transform with a data string."""
        if no_config:
            monkeypatch.setattr(
                'qutebrowser.config.configtypes.standarddir.config',
                lambda: None)

        b64 = base64.b64encode(b"test").decode('ascii')
        url = QUrl("data:text/css;charset=utf-8;base64,{}".format(b64))
        assert configtypes.UserStyleSheet().transform("test") == url


class TestDirectory:

    """Test Directory."""

    @pytest.fixture
    def klass(self):
        return configtypes.Directory

    def test_validate_empty(self, klass):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            klass().validate('')

    def test_validate_empty_none_ok(self, klass):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Directory(none_ok=True)
        t.validate('')

    def test_validate_does_not_exist(self, klass, os_mock):
        """Test validate with a directory which does not exist."""
        os_mock.path.isdir.return_value = False
        with pytest.raises(configexc.ValidationError):
            klass().validate('foobar')

    def test_validate_exists_abs(self, klass, os_mock):
        """Test validate with a directory which does exist."""
        os_mock.path.isdir.return_value = True
        os_mock.path.isabs.return_value = True
        klass().validate('foobar')

    def test_validate_exists_not_abs(self, klass, os_mock):
        """Test validate with a dir which does exist but is not absolute."""
        os_mock.path.isdir.return_value = True
        os_mock.path.isabs.return_value = False
        with pytest.raises(configexc.ValidationError):
            klass().validate('foobar')

    def test_validate_expanduser(self, klass, os_mock):
        """Test if validate expands the user correctly."""
        os_mock.path.isdir.side_effect = (lambda path:
                                          path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        klass().validate('~/foobar')
        os_mock.path.expanduser.assert_called_once_with('~/foobar')

    def test_validate_expandvars(self, klass, os_mock, monkeypatch):
        """Test if validate expands the user correctly."""
        os_mock.path.isdir.side_effect = (lambda path:
                                          path == '/home/foo/foobar')
        os_mock.path.isabs.return_value = True
        klass().validate('$HOME/foobar')
        os_mock.path.expandvars.assert_called_once_with('$HOME/foobar')

    def test_validate_invalid_encoding(self, klass, os_mock,
                                       unicode_encode_err):
        """Test validate with an invalid encoding, e.g. LC_ALL=C."""
        os_mock.path.isdir.side_effect = unicode_encode_err
        os_mock.path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            klass().validate('foobar')

    def test_transform(self, klass, os_mock):
        assert klass().transform('~/foobar') == '/home/foo/foobar'
        os_mock.path.expanduser.assert_called_once_with('~/foobar')

    def test_transform_empty(self, klass):
        """Test transform with none_ok = False and an empty value."""
        assert klass().transform('') is None


class TestWebKitByte:

    """Test WebKitBytes."""

    @pytest.fixture
    def klass(self):
        return configtypes.WebKitBytes

    @pytest.mark.parametrize('maxsize, val', [
        (None, ''),
        (None, '42'),
        (None, '56k'),
        (None, '56K'),
        (10, '10'),
        (2048, '2k'),
    ])
    def test_validate_valid(self, klass, maxsize, val):
        klass(none_ok=True, maxsize=maxsize).validate(val)

    @pytest.mark.parametrize('maxsize, val', [
        (None, ''),
        (None, '-1'),
        (None, '-1k'),
        (None, '56x'),
        (None, '56kk'),
        (10, '11'),
        (999, '1k'),
    ])
    def test_validate_invalid(self, klass, maxsize, val):
        with pytest.raises(configexc.ValidationError):
            klass(maxsize=maxsize).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('10', 10),
        ('1k', 1024),
        ('1t', 1024 ** 4),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestWebKitBytesList:

    """Test WebKitBytesList."""

    @pytest.fixture
    def klass(self):
        return configtypes.WebKitBytesList

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '23,56k,1337'),
        ({'maxsize': 2}, '2'),
        ({'maxsize': 2048}, '2k'),
        ({'length': 3}, '1,2,3'),
        ({'none_ok': True}, '23,,42'),
        ({'none_ok': True}, ''),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, '23,56kk,1337'),
        ({'maxsize': 2}, '3'),
        ({'maxsize': 2}, '3k'),
        ({}, '23,,42'),
        ({'length': 3}, '1,2'),
        ({'length': 3}, '1,2,3,4'),
        ({}, '23,,42'),
        ({}, ''),
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('1k', [1024]),
        ('23,2k,1337', [23, 2048, 1337]),
        ('23,,42', [23, None, 42]),
        ('', None),
    ])
    def test_transform_single(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestShellCommand:

    """Test ShellCommand."""

    @pytest.fixture
    def klass(self):
        return configtypes.ShellCommand

    @pytest.mark.parametrize('kwargs, val', [
        ({'none_ok': True}, ''),
        ({}, 'foobar'),
        ({'placeholder': '{}'}, 'foo {} bar'),
        ({'placeholder': '{}'}, 'foo{}bar'),
        ({'placeholder': '{}'}, 'foo "bar {}"'),
    ])
    def test_validate_valid(self, klass, kwargs, val):
        klass(**kwargs).validate(val)

    @pytest.mark.parametrize('kwargs, val', [
        ({}, ''),
        ({'placeholder': '{}'}, 'foo bar'),
        ({'placeholder': '{}'}, 'foo { } bar'),
        ({}, 'foo"'),  # not splittable with shlex
    ])
    def test_validate_invalid(self, klass, kwargs, val):
        with pytest.raises(configexc.ValidationError):
            klass(**kwargs).validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('foobar', ['foobar']),
        ('foobar baz', ['foobar', 'baz']),
        ('foo "bar baz" fish', ['foo', 'bar baz', 'fish']),
        ('', None),
    ])
    def test_transform_single(self, klass, val, expected):
        """Test transform with a single word."""
        assert klass().transform(val) == expected


class TestProxy:

    """Test Proxy."""

    @pytest.fixture
    def klass(self):
        return configtypes.Proxy

    @pytest.mark.parametrize('val', [
        '',
        'system',
        'none',
        'http://user:pass@example.com:2323/',
        'socks://user:pass@example.com:2323/',
        'socks5://user:pass@example.com:2323/',
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',
        'blah',
        ':',  # invalid URL
        'ftp://example.com/',  # invalid scheme
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_complete(self, klass):
        """Test complete."""
        actual = klass().complete()
        expected = [('system', "Use the system wide proxy."),
                    ('none', "Don't use any proxy"),
                    ('http://', 'HTTP proxy URL')]
        assert actual[:3] == expected

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('system', configtypes.SYSTEM_PROXY),
        ('none', NetworkProxy(QNetworkProxy.NoProxy)),
        ('socks://example.com/',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')),
        ('socks5://example.com',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')),
        ('socks5://example.com:2342',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2342)),
        ('socks5://foo@example.com',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo')),
        ('socks5://foo:bar@example.com',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo',
                         'bar')),
        ('socks5://foo:bar@example.com:2323',
            NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2323, 'foo',
                         'bar')),
    ])
    def test_transform(self, klass, val, expected):
        """Test transform with an empty value."""
        actual = klass().transform(val)
        if isinstance(actual, QNetworkProxy):
            actual = NetworkProxy(actual)
        assert actual == expected


class TestSearchEngineName:

    """Test SearchEngineName."""

    @pytest.fixture
    def klass(self):
        return configtypes.SearchEngineName

    @pytest.mark.parametrize('val', ['', 'foobar'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    def test_validate_empty(self, klass):
        with pytest.raises(configexc.ValidationError):
            klass().validate('')

    @pytest.mark.parametrize('val, expected', [('', None),
                                               ('foobar', 'foobar')])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestHeaderDict:

    @pytest.fixture
    def klass(self):
        return configtypes.HeaderDict

    @pytest.mark.parametrize('val', [
        '{"foo": "bar"}',
        '{"foo": "bar", "baz": "fish"}',
        '',  # empty value with none_ok=true
        '{}',  # ditto
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '["foo"]',  # valid json but not a dict
        '{"hello": 23}',  # non-string as value
        '{"hällo": "world"}',  # non-ascii data in key
        '{"hello": "wörld"}',  # non-ascii data in value
        '',  # empty value with none_ok=False
        '{}',  # ditto
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('{"foo": "bar"}', {"foo": "bar"}),
        ('{}', None),
        ('', None),
    ])
    def test_transform(self, klass, val, expected):
        assert klass(none_ok=True).transform(val) == expected


class TestSearchEngineUrl:

    """Test SearchEngineUrl."""

    @pytest.fixture
    def klass(self):
        return configtypes.SearchEngineUrl

    @pytest.mark.parametrize('val', [
        'http://example.com/?q={}',
        'http://example.com/?q={0}',
        'http://example.com/?q={0}&a={0}',
        '',  # empty value with none_ok
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',  # empty value without none_ok
        'foo',  # no placeholder
        ':{}',  # invalid URL
        'foo{bar}baz{}',  # {bar} format string variable
        '{1}{}',  # numbered format string variable
        '{{}',  # invalid format syntax
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('foobar', 'foobar'),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestFuzzyUrl:

    """Test FuzzyUrl."""

    @pytest.fixture
    def klass(self):
        return configtypes.FuzzyUrl

    @pytest.mark.parametrize('val', [
        '',
        'http://example.com/?q={}',
        'example.com',
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',
        '::foo',  # invalid URL
        'foo bar',  # invalid search term
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('example.com', QUrl('http://example.com')),
    ])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestPadding:

    """Test Padding."""

    @pytest.fixture
    def klass(self):
        return configtypes.Padding

    @pytest.mark.parametrize('val', [
        '',
        '1,,2,3',
        '1,2,3,4',
        '1, 2, 3, 4',
        '0,0,0,0',
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',
        '5',
        '1,,2,3',
        '0.5',
        '-1',
        '1,2',
        '1,2,3',
        '1,2,3,4,5',
        '1,2,-1,3',
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [
        ('', None),
        ('1,2,3,4', (1, 2, 3, 4)),
    ])
    def test_transform(self, klass, val, expected):
        """Test transforming of values."""
        transformed = klass().transform(val)
        assert transformed == expected
        if expected is not None:
            assert transformed.top == expected[0]
            assert transformed.bottom == expected[1]
            assert transformed.left == expected[2]
            assert transformed.right == expected[3]


class TestAutoSearch:

    """Test AutoSearch."""

    TESTS = {
        'naive': 'naive',
        'NAIVE': 'naive',
        'dns': 'dns',
        'DNS': 'dns',
        '': None,
    }
    TESTS.update({k: 'naive' for k, v in TestBool.TESTS.items() if v})
    TESTS.update({k: v for k, v in TestBool.TESTS.items()
                  if not v and v is not None})

    INVALID = ['ddns', 'foo', '']

    @pytest.fixture
    def klass(self):
        return configtypes.AutoSearch

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestIgnoreCase:

    """Test IgnoreCase."""

    TESTS = {
        'smart': 'smart',
        'SMART': 'smart',
    }
    TESTS.update(TestBool.TESTS)

    INVALID = ['ssmart', 'foo']

    @pytest.fixture
    def klass(self):
        return configtypes.IgnoreCase

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestEncoding:

    """Test Encoding."""

    @pytest.fixture
    def klass(self):
        return configtypes.Encoding

    @pytest.mark.parametrize('val', ['utf-8', 'UTF-8', 'iso8859-1', ''])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['blubber', ''])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', [('utf-8', 'utf-8'), ('', None)])
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestUrlList:

    """Test UrlList."""

    TESTS = {
        'http://qutebrowser.org/': [QUrl('http://qutebrowser.org/')],
        'http://qutebrowser.org/,http://heise.de/':
            [QUrl('http://qutebrowser.org/'), QUrl('http://heise.de/')],
        '': None,
    }

    @pytest.fixture
    def klass(self):
        return configtypes.UrlList

    @pytest.mark.parametrize('val', sorted(TESTS))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',
        'foo,,bar',
        '+',  # invalid URL with QUrl.fromUserInput
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    def test_validate_empty_item(self, klass):
        """Test validate with empty item and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            klass().validate('foo,,bar')

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform_single(self, klass, val, expected):
        assert klass().transform(val) == expected


class TestSessionName:

    """Test SessionName."""

    @pytest.fixture
    def klass(self):
        return configtypes.SessionName

    @pytest.mark.parametrize('val', ['', 'foobar'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', '_foo'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)


class TestConfirmQuit:

    """Test ConfirmQuit."""

    TESTS = {
        '': None,
        'always': ['always'],
        'never': ['never'],
        'multiple-tabs,downloads': ['multiple-tabs', 'downloads'],
        'downloads,multiple-tabs': ['downloads', 'multiple-tabs'],
        'downloads,,multiple-tabs': ['downloads', None, 'multiple-tabs'],
    }

    @pytest.fixture
    def klass(self):
        return configtypes.ConfirmQuit

    @pytest.mark.parametrize('val', sorted(TESTS.keys()))
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', [
        '',  # with none_ok=False
        'foo',
        'downloads,foo',  # valid value mixed with invalid one
        'downloads,,multiple-tabs',  # empty value
        'downloads,multiple-tabs,downloads',  # duplicate value
        'always,downloads',  # always combined
        'never,downloads',  # never combined
    ])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)

    @pytest.mark.parametrize('val, expected', sorted(TESTS.items()))
    def test_transform(self, klass, val, expected):
        assert klass().transform(val) == expected

    def test_complete(self, klass):
        """Test completing by doing some samples."""
        completions = [e[0] for e in klass().complete()]
        assert 'always' in completions
        assert 'never' in completions
        assert 'multiple-tabs,downloads' in completions
        for val in completions:
            assert 'always,' not in val
            assert ',always' not in val
            assert 'never,' not in val
            assert ',never' not in val


class TestFormatString:

    """Test FormatString."""

    @pytest.fixture
    def typ(self):
        return configtypes.FormatString(fields=('foo', 'bar'))

    @pytest.mark.parametrize('val', [
        'foo bar baz',
        '{foo} {bar} baz',
        '',
    ])
    def test_validate_valid(self, typ, val):
        typ.none_ok = True
        typ.validate(val)

    @pytest.mark.parametrize('val', [
        '{foo} {bar} {baz}',
        '{foo} {bar',
        '{1}',
        '',
    ])
    def test_validate_invalid(self, typ, val):
        with pytest.raises(configexc.ValidationError):
            typ.validate(val)

    def test_transform(self, typ):
        assert typ.transform('foo {bar} baz') == 'foo {bar} baz'


class TestUserAgent:

    """Test UserAgent."""

    @pytest.fixture
    def klass(self):
        return configtypes.UserAgent

    @pytest.mark.parametrize('val', [
        '',
        'Hello World! :-)',
    ])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    def test_validate_invalid(self, klass):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            klass().validate('')

    def test_transform(self, klass):
        assert klass().transform('foobar') == 'foobar'

    def test_complete(self, klass):
        """Simple smoke test for completion."""
        klass().complete()


class TestTimestampTemplate:

    """Test TimestampTemplate."""

    @pytest.fixture
    def klass(self):
        return configtypes.TimestampTemplate

    @pytest.mark.parametrize('val', ['', 'foobar', '%H:%M', 'foo %H bar %M'])
    def test_validate_valid(self, klass, val):
        klass(none_ok=True).validate(val)

    @pytest.mark.parametrize('val', ['', '%'])
    def test_validate_invalid(self, klass, val):
        with pytest.raises(configexc.ValidationError):
            klass().validate(val)


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
