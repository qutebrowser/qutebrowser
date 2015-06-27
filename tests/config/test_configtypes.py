# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import os.path
import base64
import itertools

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


@pytest.fixture
def os_path(mocker):
    """Fixture that mocks and returns os.path from the configtypes module."""
    return mocker.patch('qutebrowser.config.configtypes.os.path',
                        autospec=True)


class TestValidValues:

    """Test ValidValues."""

    def test_contains_without_desc(self):
        """Test __contains__ without a description."""
        vv = configtypes.ValidValues('foo', 'bar')
        assert 'foo' in vv
        assert 'baz' not in vv

    def test_contains_with_desc(self):
        """Test __contains__ with a description."""
        vv = configtypes.ValidValues(('foo', "foo desc"), ('bar', "bar desc"))
        assert 'foo' in vv
        assert 'bar' in vv
        assert 'baz' not in vv

    def test_contains_mixed_desc(self):
        """Test __contains__ with mixed description."""
        vv = configtypes.ValidValues(('foo', "foo desc"), 'bar')
        assert 'foo' in vv
        assert 'bar' in vv
        assert 'baz' not in vv

    def test_iter_without_desc(self):
        """Test __iter__ without a description."""
        vv = configtypes.ValidValues('foo', 'bar')
        assert list(vv) == ['foo', 'bar']

    def test_iter_with_desc(self):
        """Test __iter__ with a description."""
        vv = configtypes.ValidValues(('foo', "foo desc"), ('bar', "bar desc"))
        assert list(vv) == ['foo', 'bar']

    def test_iter_with_mixed_desc(self):
        """Test __iter__ with mixed description."""
        vv = configtypes.ValidValues(('foo', "foo desc"), 'bar')
        assert list(vv) == ['foo', 'bar']

    def test_descriptions(self):
        """Test descriptions."""
        vv = configtypes.ValidValues(('foo', "foo desc"), ('bar', "bar desc"),
                                     'baz')
        assert vv.descriptions['foo'] == "foo desc"
        assert vv.descriptions['bar'] == "bar desc"
        assert 'baz' not in vv.descriptions


class TestBaseType:

    """Test BaseType."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.BaseType()

    def test_transform(self):
        """Test transform with a value."""
        assert self.t.transform("foobar") == "foobar"

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_validate_not_implemented(self):
        """Test validate without valid_values set."""
        with pytest.raises(NotImplementedError):
            self.t.validate("foo")

    def test_validate_none_ok(self):
        """Test validate with none_ok = True."""
        t = configtypes.BaseType(none_ok=True)
        t.validate('')

    def test_validate(self):
        """Test validate with valid_values set."""
        self.t.valid_values = configtypes.ValidValues('foo', 'bar')
        self.t.validate('bar')
        with pytest.raises(configexc.ValidationError):
            self.t.validate('baz')

    def test_complete_none(self):
        """Test complete with valid_values not set."""
        assert self.t.complete() is None

    def test_complete_without_desc(self):
        """Test complete with valid_values set without description."""
        self.t.valid_values = configtypes.ValidValues('foo', 'bar')
        assert self.t.complete() == [('foo', ''), ('bar', '')]

    def test_complete_with_desc(self):
        """Test complete with valid_values set with description."""
        self.t.valid_values = configtypes.ValidValues(('foo', "foo desc"),
                                                      ('bar', "bar desc"))
        assert self.t.complete() == [('foo', "foo desc"), ('bar', "bar desc")]

    def test_complete_mixed_desc(self):
        """Test complete with valid_values set with mixed description."""
        self.t.valid_values = configtypes.ValidValues(('foo', "foo desc"),
                                                      'bar')
        assert self.t.complete() == [('foo', "foo desc"), ('bar', "")]


class TestString:

    """Test String."""

    def test_minlen_toosmall(self):
        """Test __init__ with a minlen < 1."""
        with pytest.raises(ValueError):
            configtypes.String(minlen=0)

    def test_minlen_ok(self):
        """Test __init__ with a minlen = 1."""
        configtypes.String(minlen=1)

    def test_maxlen_toosmall(self):
        """Test __init__ with a maxlen < 1."""
        with pytest.raises(ValueError):
            configtypes.String(maxlen=0)

    def test_maxlen_ok(self):
        """Test __init__ with a maxlen = 1."""
        configtypes.String(maxlen=1)

    def test_minlen_gt_maxlen(self):
        """Test __init__ with a minlen bigger than the maxlen."""
        with pytest.raises(ValueError):
            configtypes.String(minlen=2, maxlen=1)

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = configtypes.String()
        with pytest.raises(configexc.ValidationError):
            t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.String(none_ok=True)
        t.validate("")

    def test_validate(self):
        """Test validate with some random string."""
        t = configtypes.String()
        t.validate("Hello World! :-)")

    def test_validate_forbidden(self):
        """Test validate with forbidden chars."""
        t = configtypes.String(forbidden='xyz')
        t.validate("foobar")
        t.validate("foXbar")
        with pytest.raises(configexc.ValidationError):
            t.validate("foybar")
        with pytest.raises(configexc.ValidationError):
            t.validate("foxbar")

    def test_validate_minlen_toosmall(self):
        """Test validate with a minlen and a too short string."""
        t = configtypes.String(minlen=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('f')

    def test_validate_minlen_ok(self):
        """Test validate with a minlen and a good string."""
        t = configtypes.String(minlen=2)
        t.validate('fo')

    def test_validate_maxlen_toolarge(self):
        """Test validate with a maxlen and a too long string."""
        t = configtypes.String(maxlen=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('fob')

    def test_validate_maxlen_ok(self):
        """Test validate with a maxlen and a good string."""
        t = configtypes.String(maxlen=2)
        t.validate('fo')

    def test_validate_range_ok(self):
        """Test validate with both min/maxlen and a good string."""
        t = configtypes.String(minlen=2, maxlen=3)
        t.validate('fo')
        t.validate('foo')

    def test_validate_range_bad(self):
        """Test validate with both min/maxlen and a bad string."""
        t = configtypes.String(minlen=2, maxlen=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('f')
        with pytest.raises(configexc.ValidationError):
            t.validate('fooo')

    def test_transform(self):
        """Test if transform doesn't alter the value."""
        t = configtypes.String()
        assert t.transform('foobar') == 'foobar'


class TestList:

    """Test List."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.List()

    def test_validate_single(self):
        """Test validate with a single value."""
        self.t.validate('foo')

    def test_validate_multiple(self):
        """Test validate with multiple values."""
        self.t.validate('foo,bar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.List(none_ok=True)
        t.validate('')

    def test_validate_empty_item(self):
        """Test validate with empty item and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foo,,bar')

    def test_validate_empty_item_none_ok(self):
        """Test validate with empty item and none_ok = True."""
        t = configtypes.List(none_ok=True)
        with pytest.raises(configexc.ValidationError):
            t.validate('foo,,bar')

    def test_transform_single(self):
        """Test transform with a single value."""
        assert self.t.transform('foo') == ['foo']

    def test_transform_more(self):
        """Test transform with multiple values."""
        assert self.t.transform('foo,bar,baz') == ['foo', 'bar', 'baz']

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None


class TestBool:

    """Test Bool."""

    TESTS = {True: ['1', 'yes', 'YES', 'true', 'TrUe', 'on'],
             False: ['0', 'no', 'NO', 'false', 'FaLsE', 'off']}

    INVALID = ['10', 'yess', 'false_']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Bool()

    @pytest.mark.parametrize('out, inp',
                             [(out, inp) for out, inputs in TESTS.items() for
                              inp in inputs])
    def test_transform(self, out, inp):
        """Test transform with all values."""
        assert self.t.transform(inp) == out

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None

    @pytest.mark.parametrize('val', itertools.chain(*TESTS.values()))
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(val)

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = configtypes.Bool()
        with pytest.raises(configexc.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Int(none_ok=True)
        t.validate('')


class TestInt:

    """Test Int."""

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with pytest.raises(ValueError):
            configtypes.Int(minval=2, maxval=1)

    def test_validate_int(self):
        """Test validate with a normal int."""
        t = configtypes.Int()
        t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't an int."""
        t = configtypes.Int()
        with pytest.raises(configexc.ValidationError):
            t.validate('foobar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = configtypes.Int()
        with pytest.raises(configexc.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Int(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small int."""
        t = configtypes.Int(minval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good int."""
        t = configtypes.Int(minval=2)
        t.validate('2')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big int."""
        t = configtypes.Int(maxval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good int."""
        t = configtypes.Int(maxval=2)
        t.validate('2')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good int."""
        t = configtypes.Int(minval=2, maxval=3)
        t.validate('2')
        t.validate('3')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad int."""
        t = configtypes.Int(minval=2, maxval=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1')
        with pytest.raises(configexc.ValidationError):
            t.validate('4')

    def test_transform_none(self):
        """Test transform with an empty value."""
        t = configtypes.Int(none_ok=True)
        assert t.transform('') is None

    def test_transform_int(self):
        """Test transform with an int."""
        t = configtypes.Int()
        assert t.transform('1337') == 1337


class TestIntList:

    """Test IntList."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.IntList()

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate('23,42,1337')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('23,,42')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = configtypes.IntList(none_ok=True)
        t.validate('23,,42')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('23,foo,1337')

    def test_transform_single(self):
        """Test transform with a single value."""
        assert self.t.transform('1337') == [1337]

    def test_transform_more(self):
        """Test transform with multiple values."""
        assert self.t.transform('23,42,1337') == [23, 42, 1337]

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('23,,42') == [23, None, 42]


class TestFloat:

    """Test Float."""

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with pytest.raises(ValueError):
            configtypes.Float(minval=2, maxval=1)

    def test_validate_float(self):
        """Test validate with a normal float."""
        t = configtypes.Float()
        t.validate('1337.42')

    def test_validate_int(self):
        """Test validate with an int."""
        t = configtypes.Float()
        t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't an float."""
        t = configtypes.Float()
        with pytest.raises(configexc.ValidationError):
            t.validate('foobar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = configtypes.Float()
        with pytest.raises(configexc.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Float(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small float."""
        t = configtypes.Float(minval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1.99')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good float."""
        t = configtypes.Float(minval=2)
        t.validate('2.00')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big float."""
        t = configtypes.Float(maxval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('2.01')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good float."""
        t = configtypes.Float(maxval=2)
        t.validate('2.00')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good float."""
        t = configtypes.Float(minval=2, maxval=3)
        t.validate('2.00')
        t.validate('3.00')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad float."""
        t = configtypes.Float(minval=2, maxval=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1.99')
        with pytest.raises(configexc.ValidationError):
            t.validate('3.01')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        t = configtypes.Float()
        assert t.transform('') is None

    def test_transform_float(self):
        """Test transform with an float."""
        t = configtypes.Float()
        assert t.transform('1337.42') == 1337.42

    def test_transform_int(self):
        """Test transform with an int."""
        t = configtypes.Float()
        assert t.transform('1337') == 1337.00


class TestPerc:

    """Test Perc."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Perc()

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with pytest.raises(ValueError):
            configtypes.Perc(minval=2, maxval=1)

    def test_validate_int(self):
        """Test validate with a normal int (not a percentage)."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't a percentage."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('1337%%')

    def test_validate_perc(self):
        """Test validate with a percentage."""
        self.t.validate('1337%')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Perc(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small percentage."""
        t = configtypes.Perc(minval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good percentage."""
        t = configtypes.Perc(minval=2)
        t.validate('2%')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big percentage."""
        t = configtypes.Perc(maxval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3%')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good percentage."""
        t = configtypes.Perc(maxval=2)
        t.validate('2%')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good percentage."""
        t = configtypes.Perc(minval=2, maxval=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad percentage."""
        t = configtypes.Perc(minval=2, maxval=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')
        with pytest.raises(configexc.ValidationError):
            t.validate('4%')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform_perc(self):
        """Test transform with a percentage."""
        assert self.t.transform('1337%') == 1337


class TestPercList:

    """Test PercList."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.PercList()

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with pytest.raises(ValueError):
            configtypes.PercList(minval=2, maxval=1)

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate('23%,42%,1337%')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('23%,42%%,1337%')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small percentage."""
        t = configtypes.PercList(minval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good percentage."""
        t = configtypes.PercList(minval=2)
        t.validate('2%')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big percentage."""
        t = configtypes.PercList(maxval=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3%')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good percentage."""
        t = configtypes.PercList(maxval=2)
        t.validate('2%')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good percentage."""
        t = configtypes.PercList(minval=2, maxval=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad percentage."""
        t = configtypes.PercList(minval=2, maxval=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')
        with pytest.raises(configexc.ValidationError):
            t.validate('4%')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('23%,,42%')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = configtypes.PercList(none_ok=True)
        t.validate('23%,,42%')

    def test_transform_single(self):
        """Test transform with a single value."""
        assert self.t.transform('1337%') == [1337]

    def test_transform_more(self):
        """Test transform with multiple values."""
        assert self.t.transform('23%,42%,1337%') == [23, 42, 1337]

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('23%,,42%') == [23, None, 42]


class TestPercOrInt:

    """Test PercOrInt."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.PercOrInt()

    def test_minint_gt_maxint(self):
        """Test __init__ with a minint bigger than the maxint."""
        with pytest.raises(ValueError):
            configtypes.PercOrInt(minint=2, maxint=1)

    def test_minperc_gt_maxperc(self):
        """Test __init__ with a minperc bigger than the maxperc."""
        with pytest.raises(ValueError):
            configtypes.PercOrInt(minperc=2, maxperc=1)

    def test_validate_string(self):
        """Test validate with something which isn't a percentage."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('1337%%')

    def test_validate_perc(self):
        """Test validate with a percentage."""
        self.t.validate('1337%')

    def test_validate_int(self):
        """Test validate with a normal int."""
        self.t.validate('1337')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.PercOrInt(none_ok=True)
        t.validate('')

    def test_validate_minint_toosmall(self):
        """Test validate with a minint and a too small int."""
        t = configtypes.PercOrInt(minint=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1')

    def test_validate_minint_ok(self):
        """Test validate with a minint and a good int."""
        t = configtypes.PercOrInt(minint=2)
        t.validate('2')

    def test_validate_maxint_toolarge(self):
        """Test validate with a maxint and a too big int."""
        t = configtypes.PercOrInt(maxint=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3')

    def test_validate_maxint_ok(self):
        """Test validate with a maxint and a good int."""
        t = configtypes.PercOrInt(maxint=2)
        t.validate('2')

    def test_validate_int_range_ok(self):
        """Test validate with both min/maxint and a good int."""
        t = configtypes.PercOrInt(minint=2, maxint=3)
        t.validate('2')
        t.validate('3')

    def test_validate_int_range_bad(self):
        """Test validate with both min/maxint and a bad int."""
        t = configtypes.PercOrInt(minint=2, maxint=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1')
        with pytest.raises(configexc.ValidationError):
            t.validate('4')

    def test_validate_minperc_toosmall(self):
        """Test validate with a minperc and a too small perc."""
        t = configtypes.PercOrInt(minperc=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')

    def test_validate_minperc_ok(self):
        """Test validate with a minperc and a good perc."""
        t = configtypes.PercOrInt(minperc=2)
        t.validate('2%')

    def test_validate_maxperc_toolarge(self):
        """Test validate with a maxperc and a too big perc."""
        t = configtypes.PercOrInt(maxperc=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3%')

    def test_validate_maxperc_ok(self):
        """Test validate with a maxperc and a good perc."""
        t = configtypes.PercOrInt(maxperc=2)
        t.validate('2%')

    def test_validate_perc_range_ok(self):
        """Test validate with both min/maxperc and a good perc."""
        t = configtypes.PercOrInt(minperc=2, maxperc=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_perc_range_bad(self):
        """Test validate with both min/maxperc and a bad perc."""
        t = configtypes.PercOrInt(minperc=2, maxperc=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1%')
        with pytest.raises(configexc.ValidationError):
            t.validate('4%')

    def test_validate_both_range_int(self):
        """Test validate with both min/maxperc and make sure int is ok."""
        t = configtypes.PercOrInt(minperc=2, maxperc=3)
        t.validate('4')
        t.validate('1')

    def test_validate_both_range_perc(self):
        """Test validate with both min/maxint and make sure perc is ok."""
        t = configtypes.PercOrInt(minint=2, maxint=3)
        t.validate('4%')
        t.validate('1%')

    def test_transform_none(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform_perc(self):
        """Test transform with a percentage."""
        assert self.t.transform('1337%') == '1337%'

    def test_transform_int(self):
        """Test transform with an int."""
        assert self.t.transform('1337') == '1337'


class TestCommand:

    """Test Command."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, stubs):
        self.t = configtypes.Command()
        cmd_utils = stubs.FakeCmdUtils({'cmd1': stubs.FakeCommand("desc 1"),
                                        'cmd2': stubs.FakeCommand("desc 2")})
        monkeypatch.setattr('qutebrowser.config.configtypes.cmdutils',
                            cmd_utils)

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.Command(none_ok=True)
        t.validate('')

    def test_validate_command(self):
        """Test validate with a command."""
        self.t.validate('cmd1')
        self.t.validate('cmd2')

    def test_validate_command_args(self):
        """Test validate with a command and arguments."""
        self.t.validate('cmd1  foo bar')
        self.t.validate('cmd2  baz fish')

    def test_validate_invalid_command(self):
        """Test validate with an invalid command."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('cmd3')

    def test_validate_invalid_command_args(self):
        """Test validate with an invalid command and arguments."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('cmd3  foo bar')

    def test_transform(self):
        """Make sure transform doesn't alter values."""
        assert self.t.transform('foo bar') == 'foo bar'

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_complete(self):
        """Test complete."""
        items = self.t.complete()
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
    }
    INVALID = ['RRGB', 'HSV ']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.ColorSystem()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.ColorSystem(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('val', TESTS)
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError, msg=val):
            self.t.validate(val)

    @pytest.mark.parametrize('k, v', TESTS.items())
    def test_transform(self, k, v):
        """Test transform."""
        assert self.t.transform(k) == v

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None


class TestQtColor:

    """Test QtColor."""

    VALID = ['#123', '#112233', '#111222333', '#111122223333', 'red']
    INVALID = ['#00000G', '#123456789ABCD', '#12', 'foobar', '42']
    INVALID_QT = ['rgb(0, 0, 0)']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.QtColor()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.QtColor(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('v', VALID)
    def test_validate_valid(self, v):
        """Test validate with valid values."""
        self.t.validate(v)

    @pytest.mark.parametrize('val', INVALID + INVALID_QT)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError, msg=val):
            self.t.validate(val)

    @pytest.mark.parametrize('v', VALID)
    def test_transform(self, v):
        """Test transform."""
        assert self.t.transform(v) == QColor(v)

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None


class TestCssColor(TestQtColor):

    """Test CssColor."""

    VALID = TestQtColor.VALID + ['-foobar(42)']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.CssColor()

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.CssColor(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('v', VALID)
    def test_validate_valid(self, v):
        """Test validate with valid values."""
        super().test_validate_valid(v)

    @pytest.mark.parametrize('v', VALID)
    def test_transform(self, v):
        """Make sure transform doesn't alter the value."""
        assert self.t.transform(v) == v


class TestQssColor(TestQtColor):

    """Test QssColor."""

    VALID = TestQtColor.VALID + [
        'rgba(255, 255, 255, 255)', 'hsv(359, 255, 255)',
        'hsva(359, 255, 255, 255)', 'hsv(10%, 10%, 10%)',
        'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 white, stop: 0.4 '
        'gray, stop:1 green)',
        'qconicalgradient(cx:0.5, cy:0.5, angle:30, stop:0 white, stop:1 '
        '#00FF00)',
        'qradialgradient(cx:0, cy:0, radius: 1, fx:0.5, fy:0.5, stop:0 '
        'white, stop:1 green)'
    ]
    INVALID = TestQtColor.INVALID + ['rgb(1, 2, 3, 4)', 'foo(1, 2, 3)']
    INVALID_QT = []

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.QssColor()

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.QssColor(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('v', VALID)
    def test_validate_valid(self, v):
        """Test validate with valid values."""
        super().test_validate_valid(v)

    @pytest.mark.parametrize('val', INVALID + INVALID_QT)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        super().test_validate_invalid(val)

    @pytest.mark.parametrize('v', VALID)
    def test_transform(self, v):
        """Make sure transform doesn't alter the value."""
        assert self.t.transform(v) == v


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
    }

    INVALID = [
        'green "Foobar Neue"',
        'italic green "Foobar Neue"',
        'bold bold "Foobar Neue"',
        'bold italic "Foobar Neue"',
        '10pt 20px "Foobar Neue"',
        'bold',
        'italic',
        'green',
        '10pt',
        '10pt ""',
    ]

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Font()
        self.t2 = configtypes.QtFont()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.Font(none_ok=True)
        t2 = configtypes.QtFont(none_ok=True)
        t.validate('')
        t2.validate('')

    @pytest.mark.parametrize('val, attr',
                             itertools.product(TESTS, ['t', 't2']))
    def test_validate_valid(self, val, attr):
        """Test validate with valid values."""
        getattr(self, attr).validate(val)

    @pytest.mark.parametrize('val, attr',
                             itertools.product(INVALID, ['t', 't2']))
    @pytest.mark.xfail(reason='FIXME: #103')
    def test_validate_invalid(self, val, attr):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError, msg=val):
            getattr(self, attr).validate(val)

    @pytest.mark.parametrize('string, desc', TESTS.items())
    def test_transform(self, string, desc):
        """Test transform."""
        assert self.t.transform(string) == string
        assert Font(self.t2.transform(string)) == Font.fromdesc(desc)

    def test_transform_float(self):
        """Test QtFont's transform with a float as point size.

        We can't test the point size for equality as Qt seems to do some
        rounding as appropriate.
        """
        value = Font(self.t2.transform('10.5pt "Foobar Neue"'))
        assert value.family() == 'Foobar Neue'
        assert value.weight() == QFont.Normal
        assert value.style() == QFont.StyleNormal
        assert value.pointSize() >= 10
        assert value.pointSize() <= 11

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None
        assert self.t2.transform('') is None


class TestFontFamily:

    """Test FontFamily."""

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

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.FontFamily()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.FontFamily(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('val', TESTS)
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(val)

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None


class TestRegex:

    """Test Regex."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Regex()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = configtypes.Regex(none_ok=True)
        t.validate('')

    def test_validate(self):
        """Test validate with a valid regex."""
        self.t.validate(r'(foo|bar)?baz[fis]h')

    def test_validate_invalid(self):
        """Test validate with an invalid regex."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(r'(foo|bar))?baz[fis]h')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform(self):
        """Test transform."""
        assert self.t.transform(r'foobar') == re.compile(r'foobar')


class TestRegexList:

    """Test RegexList."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.RegexList()

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate(r'(foo|bar),[abcd]?,1337{42}')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(r'(foo|bar),,1337{42}')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = configtypes.RegexList(none_ok=True)
        t.validate(r'(foo|bar),,1337{42}')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(r'(foo|bar),((),1337{42}')

    def test_transform_single(self):
        """Test transform with a single value."""
        assert self.t.transform('foo') == [re.compile('foo')]

    def test_transform_more(self):
        """Test transform with multiple values."""
        expected = [re.compile('foo'), re.compile('bar'), re.compile('baz')]
        assert self.t.transform('foo,bar,baz') == expected

    def test_transform_empty(self):
        """Test transform with an empty value."""
        expected = [re.compile('foo'), None, re.compile('bar')]
        assert self.t.transform('foo,,bar') == expected


class TestFile:

    """Test File."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.File()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.File(none_ok=True)
        t.validate("")

    def test_validate_does_not_exist(self, os_path):
        """Test validate with a file which does not exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.expandvars.side_effect = lambda x: x
        os_path.isfile.return_value = False
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_validate_exists_abs(self, os_path):
        """Test validate with a file which does exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.expandvars.side_effect = lambda x: x
        os_path.isfile.return_value = True
        os_path.isabs.return_value = True
        self.t.validate('foobar')

    def test_validate_exists_rel(self, os_path, monkeypatch):
        """Test validate with a relative path to an existing file."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config',
            lambda: '/home/foo/.config/')
        os_path.expanduser.side_effect = lambda x: x
        os_path.expandvars.side_effect = lambda x: x
        os_path.isfile.return_value = True
        os_path.isabs.return_value = False
        self.t.validate('foobar')
        os_path.join.assert_called_once_with('/home/foo/.config/', 'foobar')

    def test_validate_rel_config_none(self, os_path, monkeypatch):
        """Test with a relative path and standarddir.config returning None."""
        monkeypatch.setattr(
            'qutebrowser.config.configtypes.standarddir.config', lambda: None)
        os_path.isabs.return_value = False
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_validate_expanduser(self, os_path):
        """Test if validate expands the user correctly."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        os_path.expandvars.side_effect = lambda x: x
        os_path.isfile.side_effect = lambda path: path == '/home/foo/foobar'
        os_path.isabs.return_value = True
        self.t.validate('~/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_validate_expandvars(self, os_path):
        """Test if validate expands the environment vars correctly."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.expandvars.side_effect = lambda x: x.replace(
            '$HOME', '/home/foo')
        os_path.isfile.side_effect = lambda path: path == '/home/foo/foobar'
        os_path.isabs.return_value = True
        self.t.validate('$HOME/foobar')
        os_path.expandvars.assert_called_once_with('$HOME/foobar')

    def test_validate_invalid_encoding(self, os_path, unicode_encode_err):
        """Test validate with an invalid encoding, e.g. LC_ALL=C."""
        os_path.isfile.side_effect = unicode_encode_err
        os_path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_transform(self, os_path):
        """Test transform."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        os_path.expandvars.side_effect = lambda x: x
        assert self.t.transform('~/foobar') == '/home/foo/foobar'
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestDirectory:

    """Test Directory."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Directory()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Directory(none_ok=True)
        t.validate("")

    def test_validate_does_not_exist(self, os_path):
        """Test validate with a directory which does not exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isdir.return_value = False
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_validate_exists_abs(self, os_path):
        """Test validate with a directory which does exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isdir.return_value = True
        os_path.isabs.return_value = True
        self.t.validate('foobar')

    def test_validate_exists_not_abs(self, os_path):
        """Test validate with a dir which does exist but is not absolute."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isdir.return_value = True
        os_path.isabs.return_value = False
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_validate_expanduser(self, os_path):
        """Test if validate expands the user correctly."""
        os_path.expandvars.side_effect = lambda x: x
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        os_path.isdir.side_effect = lambda path: path == '/home/foo/foobar'
        os_path.isabs.return_value = True
        self.t.validate('~/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_validate_expandvars(self, os_path, monkeypatch):
        """Test if validate expands the user correctly."""
        os_path.expandvars.side_effect = lambda x: x.replace('$BAR',
                                                             '/home/foo/bar')
        os_path.expanduser.side_effect = lambda x: x
        os_path.isdir.side_effect = lambda path: path == '/home/foo/bar/foobar'
        os_path.isabs.return_value = True
        monkeypatch.setenv('BAR', '/home/foo/bar')
        self.t.validate('$BAR/foobar')
        os_path.expandvars.assert_called_once_with('$BAR/foobar')

    def test_validate_invalid_encoding(self, os_path, unicode_encode_err):
        """Test validate with an invalid encoding, e.g. LC_ALL=C."""
        os_path.isdir.side_effect = unicode_encode_err
        os_path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_transform(self, os_path):
        """Test transform."""
        os_path.expandvars.side_effect = lambda x: x
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        assert self.t.transform('~/foobar') == '/home/foo/foobar'
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestWebKitByte:

    """Test WebKitBytes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.WebKitBytes()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        # Note WebKitBytes are always None-able
        self.t.validate('')

    def test_validate_int(self):
        """Test validate with a normal int."""
        self.t.validate('42')

    def test_validate_int_suffix(self):
        """Test validate with an int with a suffix."""
        self.t.validate('56k')

    def test_validate_int_caps_suffix(self):
        """Test validate with an int with a capital suffix."""
        self.t.validate('56K')

    def test_validate_int_negative(self):
        """Test validate with a negative int."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('-1')

    def test_validate_int_negative_suffix(self):
        """Test validate with a negative int with suffix."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('-1k')

    def test_validate_int_toobig(self):
        """Test validate with an int which is too big."""
        t = configtypes.WebKitBytes(maxsize=10)
        with pytest.raises(configexc.ValidationError):
            t.validate('11')

    def test_validate_int_not_toobig(self):
        """Test validate with an int which is not too big."""
        t = configtypes.WebKitBytes(maxsize=10)
        t.validate('10')

    def test_validate_int_toobig_suffix(self):
        """Test validate with an int which is too big with suffix."""
        t = configtypes.WebKitBytes(maxsize=10)
        with pytest.raises(configexc.ValidationError):
            t.validate('1k')

    def test_validate_int_invalid_suffix(self):
        """Test validate with an int with an invalid suffix."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('56x')

    def test_validate_int_double_suffix(self):
        """Test validate with an int with a double suffix."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('56kk')

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None

    def test_transform_int(self):
        """Test transform with a simple value."""
        assert self.t.transform('10') == 10

    def test_transform_int_suffix(self):
        """Test transform with a value with suffix."""
        assert self.t.transform('1k') == 1024


class TestWebKitBytesList:

    """Test WebKitBytesList."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.WebKitBytesList()

    def test_validate_good(self):
        """Test validate with good values."""
        t = configtypes.WebKitBytesList()
        t.validate('23,56k,1337')

    def test_validate_bad(self):
        """Test validate with bad values."""
        t = configtypes.WebKitBytesList()
        with pytest.raises(configexc.ValidationError):
            t.validate('23,56kk,1337')

    def test_validate_maxsize_toolarge(self):
        """Test validate with a maxsize and a too big size."""
        t = configtypes.WebKitBytesList(maxsize=2)
        with pytest.raises(configexc.ValidationError):
            t.validate('3')
        with pytest.raises(configexc.ValidationError):
            t.validate('3k')

    def test_validate_maxsize_ok(self):
        """Test validate with a maxsize and a good size."""
        t = configtypes.WebKitBytesList(maxsize=2)
        t.validate('2')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('23,,42')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = configtypes.WebKitBytesList(none_ok=True)
        t.validate('23,,42')

    def test_validate_len_tooshort(self):
        """Test validate with a too short length."""
        t = configtypes.WebKitBytesList(length=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1,2')

    def test_validate_len_ok(self):
        """Test validate with a correct length."""
        t = configtypes.WebKitBytesList(length=3)
        t.validate('1,2,3')

    def test_validate_len_toolong(self):
        """Test validate with a too long length."""
        t = configtypes.WebKitBytesList(length=3)
        with pytest.raises(configexc.ValidationError):
            t.validate('1,2,3,4')

    def test_transform_single(self):
        """Test transform with a single value."""
        assert self.t.transform('1k') == [1024]

    def test_transform_more(self):
        """Test transform with multiple values."""
        assert self.t.transform('23,2k,1337'), [23, 2048, 1337]

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('23,,42'), [23, None, 42]


class TestShellCommand:

    """Test ShellCommand."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.ShellCommand()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.ShellCommand(none_ok=True)
        t.validate("")

    def test_validate_simple(self):
        """Test validate with a simple string."""
        self.t.validate('foobar')

    def test_validate_placeholder(self):
        """Test validate with a placeholder."""
        t = configtypes.ShellCommand(placeholder='{}')
        t.validate('foo {} bar')

    def test_validate_placeholder_invalid(self):
        """Test validate with an invalid placeholder."""
        t = configtypes.ShellCommand(placeholder='{}')
        with pytest.raises(configexc.ValidationError):
            t.validate('foo{} bar')

    def test_transform_single(self):
        """Test transform with a single word."""
        assert self.t.transform('foobar') == ['foobar']

    def test_transform_double(self):
        """Test transform with two words."""
        assert self.t.transform('foobar baz'), ['foobar', 'baz']

    def test_transform_quotes(self):
        """Test transform with a quoted word."""
        expected = ['foo', 'bar baz', 'fish']
        assert self.t.transform('foo "bar baz" fish') == expected

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestProxy:

    """Test Proxy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Proxy()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Proxy(none_ok=True)
        t.validate('')

    def test_validate_system(self):
        """Test validate with system proxy."""
        self.t.validate('system')

    def test_validate_none(self):
        """Test validate with none proxy."""
        self.t.validate('none')

    def test_validate_invalid(self):
        """Test validate with an invalid URL."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(':')

    def test_validate_scheme(self):
        """Test validate with a URL with wrong scheme."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('ftp://example.com/')

    def test_validate_http(self):
        """Test validate with a correct HTTP URL."""
        self.t.validate('http://user:pass@example.com:2323/')

    def test_validate_socks(self):
        """Test validate with a correct socks URL."""
        self.t.validate('socks://user:pass@example.com:2323/')

    def test_validate_socks5(self):
        """Test validate with a correct socks5 URL."""
        self.t.validate('socks5://user:pass@example.com:2323/')

    def test_complete(self):
        """Test complete."""
        actual = self.t.complete()
        expected = [('system', "Use the system wide proxy."),
                    ('none', "Don't use any proxy"),
                    ('http://', 'HTTP proxy URL'),
                    ('socks://', 'SOCKS proxy URL')]
        assert actual == expected

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform_system(self):
        """Test transform with system proxy."""
        assert self.t.transform('system') is configtypes.SYSTEM_PROXY

    def test_transform_none(self):
        """Test transform with no proxy."""
        actual = NetworkProxy(self.t.transform('none'))
        expected = NetworkProxy(QNetworkProxy.NoProxy)
        assert actual == expected

    def test_transform_socks(self):
        """Test transform with a socks proxy."""
        actual = NetworkProxy(self.t.transform('socks://example.com/'))
        expected = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')
        assert actual == expected

    def test_transform_socks5(self):
        """Test transform with a socks5 proxy."""
        actual = NetworkProxy(self.t.transform('socks5://example.com'))
        expected = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')
        assert actual == expected

    def test_transform_http_port(self):
        """Test transform with a http proxy with set port."""
        actual = NetworkProxy(self.t.transform('socks5://example.com:2342'))
        expected = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2342)
        assert actual == expected

    def test_transform_socks_user(self):
        """Test transform with a socks proxy with set user."""
        actual = NetworkProxy(self.t.transform('socks5://foo@example.com'))
        expected = NetworkProxy(
            QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo')
        assert actual == expected

    def test_transform_socks_user_password(self):
        """Test transform with a socks proxy with set user/password."""
        actual = NetworkProxy(self.t.transform('socks5://foo:bar@example.com'))
        expected = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0,
                                'foo', 'bar')
        assert actual == expected

    def test_transform_socks_user_password_port(self):
        """Test transform with a socks proxy with set port/user/password."""
        actual = NetworkProxy(
            self.t.transform('socks5://foo:bar@example.com:2323'))
        expected = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2323,
                                'foo', 'bar')
        assert actual == expected


class TestSearchEngineName:

    """Test SearchEngineName."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.SearchEngineName()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.SearchEngineName(none_ok=True)
        t.validate('')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform(self):
        """Test transform with a value."""
        assert self.t.transform("foobar") == "foobar"


class TestSearchEngineUrl:

    """Test SearchEngineUrl."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.SearchEngineUrl()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.SearchEngineUrl(none_ok=True)
        t.validate('')

    def test_validate_no_placeholder(self):
        """Test validate with no placeholder."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foo')

    def test_validate(self):
        """Test validate with a good value."""
        self.t.validate('http://example.com/?q={}')

    def test_validate_invalid_url(self):
        """Test validate with an invalid URL."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(':{}')

    def test_validate_format_string(self):
        """Test validate with a {foo} format string."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foo{bar}baz{}')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform(self):
        """Test transform with a value."""
        assert self.t.transform("foobar") == "foobar"


class TestFuzzyUrl:

    """Test FuzzyUrl."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.FuzzyUrl()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.FuzzyUrl(none_ok=True)
        t.validate('')

    def test_validate(self):
        """Test validate with a good value."""
        self.t.validate('http://example.com/?q={}')

    def test_validate_good_fuzzy(self):
        """Test validate with a good fuzzy value."""
        self.t.validate('example.com')

    def test_validate_invalid_url(self):
        """Test validate with an invalid URL."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('::foo')

    def test_validate_invalid_search(self):
        """Test validate with an invalid search term."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foo bar')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform(self):
        """Test transform with a value."""
        assert self.t.transform("example.com") == QUrl('http://example.com')


class TestUserStyleSheet:

    """Test UserStyleSheet."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.UserStyleSheet()

    def test_validate_invalid_encoding(self, mocker, unicode_encode_err):
        """Test validate with an invalid encoding, e.g. LC_ALL=C."""
        os_path = mocker.patch('qutebrowser.config.configtypes.os.path',
                               autospec=True)
        os_path.isfile.side_effect = unicode_encode_err
        os_path.isabs.side_effect = unicode_encode_err
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foobar')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None

    def test_transform_file(self, os_path, mocker):
        """Test transform with a filename."""
        qurl = mocker.patch('qutebrowser.config.configtypes.QUrl',
                            autospec=True)
        qurl.fromLocalFile.return_value = QUrl("file:///foo/bar")
        os_path.exists.return_value = True
        path = os.path.join(os.path.sep, 'foo', 'bar')
        assert self.t.transform(path) == QUrl("file:///foo/bar")

    def test_transform_file_expandvars(self, os_path, monkeypatch, mocker):
        """Test transform with a filename (expandvars)."""
        qurl = mocker.patch('qutebrowser.config.configtypes.QUrl',
                            autospec=True)
        qurl.fromLocalFile.return_value = QUrl("file:///foo/bar")
        os_path.exists.return_value = True
        monkeypatch.setenv('FOO', 'foo')
        path = os.path.join(os.path.sep, '$FOO', 'bar')
        assert self.t.transform(path) == QUrl("file:///foo/bar")

    def test_transform_base64(self):
        """Test transform with a data string."""
        b64 = base64.b64encode(b"test").decode('ascii')
        url = QUrl("data:text/css;charset=utf-8;base64,{}".format(b64))
        assert self.t.transform("test") == url


class TestAutoSearch:

    """Test AutoSearch."""

    TESTS = {
        'naive': ['naive', 'NAIVE'] + TestBool.TESTS[True],
        'dns': ['dns', 'DNS'],
        False: TestBool.TESTS[False],
    }
    INVALID = ['ddns', 'foo']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.AutoSearch()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.AutoSearch(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('val', [val for vallist in TESTS.values()
                                     for val in vallist])
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(val)

    @pytest.mark.parametrize('out, inp',
                             [(out, inp) for (out, inputs) in TESTS.items()
                              for inp in inputs])
    def test_transform(self, out, inp):
        """Test transform with all values."""
        assert self.t.transform(inp) == out

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestIgnoreCase:

    """Test IgnoreCase."""

    TESTS = {
        'smart': ['smart', 'SMART'],
        True: TestBool.TESTS[True],
        False: TestBool.TESTS[False],
    }
    INVALID = ['ssmart', 'foo']

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.IgnoreCase()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.IgnoreCase(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('val',
                             [val for vallist in TESTS.values() for val in
                              vallist])
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    @pytest.mark.parametrize('val', INVALID)
    def test_validate_invalid(self, val):
        """Test validate with invalid values."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate(val)

    @pytest.mark.parametrize('out, inp',
                             [(out, inp) for (out, inputs) in TESTS.items()
                              for inp in inputs])
    def test_transform(self, out, inp):
        """Test transform with all values."""
        assert self.t.transform(inp) == out

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestEncoding:

    """Test Encoding."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.Encoding()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.Encoding(none_ok=True)
        t.validate('')

    @pytest.mark.parametrize('val', ('utf-8', 'UTF-8', 'iso8859-1'))
    def test_validate_valid(self, val):
        """Test validate with valid values."""
        self.t.validate(val)

    def test_validate_invalid(self):
        """Test validate with an invalid value."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('blubber')

    def test_transform(self):
        """Test if transform doesn't alter the value."""
        assert self.t.transform('utf-8') == 'utf-8'

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        assert self.t.transform('') is None


class TestUrlList:

    """Test UrlList."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.UrlList()

    def test_validate_single(self):
        """Test validate with a single value."""
        self.t.validate('http://www.qutebrowser.org/')

    def test_validate_multiple(self):
        """Test validate with multiple values."""
        self.t.validate('http://www.qutebrowser.org/,htpt://www.heise.de/')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.UrlList(none_ok=True)
        t.validate('')

    def test_validate_empty_item(self):
        """Test validate with empty item and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('foo,,bar')

    def test_validate_empty_item_none_ok(self):
        """Test validate with empty item and none_ok = True."""
        t = configtypes.UrlList(none_ok=True)
        with pytest.raises(configexc.ValidationError):
            t.validate('foo,,bar')

    def test_transform_single(self):
        """Test transform with a single value."""
        actual = self.t.transform('http://qutebrowser.org/')
        expected = [QUrl('http://qutebrowser.org/')]
        assert actual == expected

    def test_transform_more(self):
        """Test transform with multiple values."""
        actual = self.t.transform('http://qutebrowser.org/,http://heise.de/')
        expected = [QUrl('http://qutebrowser.org/'), QUrl('http://heise.de/')]
        assert actual == expected

    def test_transform_empty(self):
        """Test transform with an empty value."""
        assert self.t.transform('') is None


class TestFormatString:

    """Test FormatString."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.FormatString(fields=('foo', 'bar'))

    def test_transform(self):
        """Test if transform doesn't alter the value."""
        assert self.t.transform('foo {bar} baz') == 'foo {bar} baz'

    def test_validate_simple(self):
        """Test validate with a simple string."""
        self.t.validate('foo bar baz')

    def test_validate_placeholders(self):
        """Test validate with placeholders."""
        self.t.validate('{foo} {bar} baz')

    def test_validate_invalid_placeholders(self):
        """Test validate with invalid placeholders."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('{foo} {bar} {baz}')

    def test_validate_invalid_placeholders_syntax(self):
        """Test validate with invalid placeholders syntax."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('{foo} {bar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.FormatString(none_ok=True, fields=())
        t.validate('')


class TestUserAgent:

    """Test UserAgent."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.t = configtypes.UserAgent()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with pytest.raises(configexc.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = configtypes.UserAgent(none_ok=True)
        t.validate("")

    def test_validate(self):
        """Test validate with some random string."""
        self.t.validate("Hello World! :-)")

    def test_transform(self):
        """Test if transform doesn't alter the value."""
        assert self.t.transform('foobar') == 'foobar'
