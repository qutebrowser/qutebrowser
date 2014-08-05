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

"""Tests for qutebrowser.config.conftypes."""

import unittest
import unittest.mock as mock
import re

import qutebrowser.config.conftypes as conftypes
from qutebrowser.test.stubs import FakeCmdUtils, FakeCommand

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtNetwork import QNetworkProxy


class Font(QFont):

    """A QFont with a nicer repr()."""

    def __repr__(self):
        return 'Font("{}", {}, {}, {})'.format(
            self.family(), self.pointSize(), self.weight(),
            self.style() & QFont.StyleItalic)

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
        return 'QNetworkProxy({}, "{}", {}, "{}", "{}")'.format(
            self.type(), self.hostName(), self.port(), self.user(),
            self.password())


class ValidValuesTest(unittest.TestCase):

    """Test ValidValues."""

    def test_contains_without_desc(self):
        """Test __contains__ without a description."""
        vv = conftypes.ValidValues('foo', 'bar')
        self.assertIn('foo', vv)
        self.assertNotIn("baz", vv)

    def test_contains_with_desc(self):
        """Test __contains__ with a description."""
        vv = conftypes.ValidValues(('foo', "foo desc"),
                                   ('bar', "bar desc"))
        self.assertIn('foo', vv)
        self.assertIn('bar', vv)
        self.assertNotIn("baz", vv)

    def test_contains_mixed_desc(self):
        """Test __contains__ with mixed description."""
        vv = conftypes.ValidValues(('foo', "foo desc"),
                                   'bar')
        self.assertIn('foo', vv)
        self.assertIn('bar', vv)
        self.assertNotIn("baz", vv)

    def test_iter_without_desc(self):
        """Test __iter__ without a description."""
        vv = conftypes.ValidValues('foo', 'bar')
        self.assertEqual(list(vv), ['foo', 'bar'])

    def test_iter_with_desc(self):
        """Test __iter__ with a description."""
        vv = conftypes.ValidValues(('foo', "foo desc"),
                                   ('bar', "bar desc"))
        self.assertEqual(list(vv), ['foo', 'bar'])

    def test_iter_with_mixed_desc(self):
        """Test __iter__ with mixed description."""
        vv = conftypes.ValidValues(('foo', "foo desc"),
                                   'bar')
        self.assertEqual(list(vv), ['foo', 'bar'])

    def test_descriptions(self):
        """Test descriptions."""
        vv = conftypes.ValidValues(('foo', "foo desc"),
                                   ('bar', "bar desc"),
                                   'baz')
        self.assertEqual(vv.descriptions['foo'], "foo desc")
        self.assertEqual(vv.descriptions['bar'], "bar desc")
        self.assertNotIn('baz', vv.descriptions)


class BaseTypeTests(unittest.TestCase):

    """Test BaseType."""

    def setUp(self):
        self.t = conftypes.BaseType()

    def test_transform(self):
        """Test transform with a value."""
        self.assertEqual(self.t.transform("foobar"), "foobar")

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_validate_not_implemented(self):
        """Test validate without valid_values set."""
        with self.assertRaises(NotImplementedError):
            self.t.validate("foo")

    def test_validate_none_ok(self):
        """Test validate with none_ok = True."""
        t = conftypes.BaseType(none_ok=True)
        t.validate('')

    def test_validate(self):
        """Test validate with valid_values set."""
        self.t.valid_values = conftypes.ValidValues('foo', 'bar')
        self.t.validate('bar')
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('baz')

    def test_complete_none(self):
        """Test complete with valid_values not set."""
        self.assertIsNone(self.t.complete())

    def test_complete_without_desc(self):
        """Test complete with valid_values set without description."""
        self.t.valid_values = conftypes.ValidValues('foo', 'bar')
        self.assertEqual(self.t.complete(), [('foo', ''), ('bar', '')])

    def test_complete_with_desc(self):
        """Test complete with valid_values set with description."""
        self.t.valid_values = conftypes.ValidValues(('foo', "foo desc"),
                                                    ('bar', "bar desc"))
        self.assertEqual(self.t.complete(), [('foo', "foo desc"),
                                             ('bar', "bar desc")])

    def test_complete_mixed_desc(self):
        """Test complete with valid_values set with mixed description."""
        self.t.valid_values = conftypes.ValidValues(('foo', "foo desc"),
                                                    'bar')
        self.assertEqual(self.t.complete(), [('foo', "foo desc"),
                                             ('bar', "")])


class StringTests(unittest.TestCase):

    """Test String."""

    def test_minlen_toosmall(self):
        """Test __init__ with a minlen < 1."""
        with self.assertRaises(ValueError):
            conftypes.String(minlen=0)

    def test_minlen_ok(self):
        """Test __init__ with a minlen = 1."""
        conftypes.String(minlen=1)

    def test_maxlen_toosmall(self):
        """Test __init__ with a maxlen < 1."""
        with self.assertRaises(ValueError):
            conftypes.String(maxlen=0)

    def test_maxlen_ok(self):
        """Test __init__ with a maxlen = 1."""
        conftypes.String(maxlen=1)

    def test_minlen_gt_maxlen(self):
        """Test __init__ with a minlen bigger than the maxlen."""
        with self.assertRaises(ValueError):
            conftypes.String(minlen=2, maxlen=1)

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = conftypes.String()
        with self.assertRaises(conftypes.ValidationError):
            t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.String(none_ok=True)
        t.validate("")

    def test_validate(self):
        """Test validate with some random string."""
        t = conftypes.String()
        t.validate("Hello World! :-)")

    def test_validate_forbidden(self):
        """Test validate with forbidden chars."""
        t = conftypes.String(forbidden='xyz')
        t.validate("foobar")
        t.validate("foXbar")
        with self.assertRaises(conftypes.ValidationError):
            t.validate("foybar")
        with self.assertRaises(conftypes.ValidationError):
            t.validate("foxbar")

    def test_validate_minlen_toosmall(self):
        """Test validate with a minlen and a too short string."""
        t = conftypes.String(minlen=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('f')

    def test_validate_minlen_ok(self):
        """Test validate with a minlen and a good string."""
        t = conftypes.String(minlen=2)
        t.validate('fo')

    def test_validate_maxlen_toolarge(self):
        """Test validate with a maxlen and a too long string."""
        t = conftypes.String(maxlen=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('fob')

    def test_validate_maxlen_ok(self):
        """Test validate with a maxlen and a good string."""
        t = conftypes.String(maxlen=2)
        t.validate('fo')

    def test_validate_range_ok(self):
        """Test validate with both min/maxlen and a good string."""
        t = conftypes.String(minlen=2, maxlen=3)
        t.validate('fo')
        t.validate('foo')

    def test_validate_range_bad(self):
        """Test validate with both min/maxlen and a bad string."""
        t = conftypes.String(minlen=2, maxlen=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('f')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('fooo')

    def test_transform(self):
        """Test if transform doesn't alter the value."""
        t = conftypes.String()
        self.assertEqual(t.transform('foobar'), 'foobar')


class ListTests(unittest.TestCase):

    """Test List."""

    def setUp(self):
        self.t = conftypes.List()

    def test_transform_single(self):
        """Test transform with a single value."""
        self.assertEqual(self.t.transform('foo'), ['foo'])

    def test_transform_more(self):
        """Test transform with multiple values."""
        self.assertEqual(self.t.transform('foo,bar,baz'),
                         ['foo', 'bar', 'baz'])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertEqual(self.t.transform('foo,,baz'),
                         ['foo', None, 'baz'])


class BoolTests(unittest.TestCase):

    TESTS = {True: ['1', 'yes', 'YES', 'true', 'TrUe', 'on'],
             False: ['0', 'no', 'NO', 'false', 'FaLsE', 'off']}

    INVALID = ['10', 'yess', 'false_']

    def setUp(self):
        self.t = conftypes.Bool()

    def test_transform(self):
        """Test transform with all values."""
        for out, inputs in self.TESTS.items():
            for inp in inputs:
                self.assertEqual(self.t.transform(inp), out, inp)

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_validate_valid(self):
        """Test validate with valid values."""
        for vallist in self.TESTS.values():
            for val in vallist:
                self.t.validate(val)

    def test_validate_invalid(self):
        """Test validate with invalid values."""
        for val in self.INVALID:
            with self.assertRaises(conftypes.ValidationError):
                self.t.validate(val)

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = conftypes.Bool()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Int(none_ok=True)
        t.validate('')



class IntTests(unittest.TestCase):

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with self.assertRaises(ValueError):
            conftypes.Int(minval=2, maxval=1)

    def test_validate_int(self):
        """Test validate with a normal int."""
        t = conftypes.Int()
        t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't an int."""
        t = conftypes.Int()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('foobar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = conftypes.Int()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Int(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small int."""
        t = conftypes.Int(minval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good int."""
        t = conftypes.Int(minval=2)
        t.validate('2')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big int."""
        t = conftypes.Int(maxval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good int."""
        t = conftypes.Int(maxval=2)
        t.validate('2')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good int."""
        t = conftypes.Int(minval=2, maxval=3)
        t.validate('2')
        t.validate('3')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad int."""
        t = conftypes.Int(minval=2, maxval=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('4')

    def test_transform_none(self):
        """Test transform with an empty value."""
        t = conftypes.Int(none_ok=True)
        self.assertIsNone(t.transform(''))

    def test_transform_int(self):
        """Test transform with an int."""
        t = conftypes.Int()
        self.assertEqual(t.transform('1337'), 1337)


class IntListTests(unittest.TestCase):

    """Test IntList."""

    def setUp(self):
        self.t = conftypes.IntList()

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate('23,42,1337')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('23,,42')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = conftypes.IntList(none_ok=True)
        t.validate('23,,42')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('23,foo,1337')

    def test_transform_single(self):
        """Test transform with a single value."""
        self.assertEqual(self.t.transform('1337'), [1337])

    def test_transform_more(self):
        """Test transform with multiple values."""
        self.assertEqual(self.t.transform('23,42,1337'),
                         [23, 42, 1337])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertEqual(self.t.transform('23,,42'), [23, None, 42])


class FloatTests(unittest.TestCase):

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with self.assertRaises(ValueError):
            conftypes.Float(minval=2, maxval=1)

    def test_validate_float(self):
        """Test validate with a normal float."""
        t = conftypes.Float()
        t.validate('1337.42')

    def test_validate_int(self):
        """Test validate with an int."""
        t = conftypes.Float()
        t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't an float."""
        t = conftypes.Float()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('foobar')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        t = conftypes.Float()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Float(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small float."""
        t = conftypes.Float(minval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1.99')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good float."""
        t = conftypes.Float(minval=2)
        t.validate('2.00')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big float."""
        t = conftypes.Float(maxval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('2.01')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good float."""
        t = conftypes.Float(maxval=2)
        t.validate('2.00')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good float."""
        t = conftypes.Float(minval=2, maxval=3)
        t.validate('2.00')
        t.validate('3.00')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad float."""
        t = conftypes.Float(minval=2, maxval=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1.99')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3.01')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad float."""
        t = conftypes.Float(minval=2, maxval=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1.99')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3.01')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        t = conftypes.Float()
        self.assertIsNone(t.transform(''))

    def test_transform_float(self):
        """Test transform with an float."""
        t = conftypes.Float()
        self.assertEqual(t.transform('1337.42'), 1337.42)

    def test_transform_int(self):
        """Test transform with an int."""
        t = conftypes.Float()
        self.assertEqual(t.transform('1337'), 1337.00)


class PercTests(unittest.TestCase):

    """Test Perc."""

    def setUp(self):
        self.t = conftypes.Perc()

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with self.assertRaises(ValueError):
            conftypes.Perc(minval=2, maxval=1)

    def test_validate_int(self):
        """Test validate with a normal int (not a percentage)."""
        with self.assertRaises(ValueError):
            self.t.validate('1337')

    def test_validate_string(self):
        """Test validate with something which isn't a percentage."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('1337%%')

    def test_validate_perc(self):
        """Test validate with a percentage."""
        self.t.validate('1337%')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Perc(none_ok=True)
        t.validate('')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small percentage."""
        t = conftypes.Perc(minval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good percentage."""
        t = conftypes.Perc(minval=2)
        t.validate('2%')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big percentage."""
        t = conftypes.Perc(maxval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3%')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good percentage."""
        t = conftypes.Perc(maxval=2)
        t.validate('2%')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good percentage."""
        t = conftypes.Perc(minval=2, maxval=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad percentage."""
        t = conftypes.Perc(minval=2, maxval=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('4%')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform_perc(self):
        """Test transform with a percentage."""
        self.assertEqual(self.t.transform('1337%'), 1337)


class PercListTests(unittest.TestCase):

    """Test PercList."""

    def setUp(self):
        self.t = conftypes.PercList()

    def test_minval_gt_maxval(self):
        """Test __init__ with a minval bigger than the maxval."""
        with self.assertRaises(ValueError):
            conftypes.PercList(minval=2, maxval=1)

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate('23%,42%,1337%')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('23%,42%%,1337%')

    def test_validate_minval_toosmall(self):
        """Test validate with a minval and a too small percentage."""
        t = conftypes.PercList(minval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')

    def test_validate_minval_ok(self):
        """Test validate with a minval and a good percentage."""
        t = conftypes.PercList(minval=2)
        t.validate('2%')

    def test_validate_maxval_toolarge(self):
        """Test validate with a maxval and a too big percentage."""
        t = conftypes.PercList(maxval=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3%')

    def test_validate_maxval_ok(self):
        """Test validate with a maxval and a good percentage."""
        t = conftypes.PercList(maxval=2)
        t.validate('2%')

    def test_validate_range_ok(self):
        """Test validate with both min/maxval and a good percentage."""
        t = conftypes.PercList(minval=2, maxval=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_range_bad(self):
        """Test validate with both min/maxval and a bad percentage."""
        t = conftypes.PercList(minval=2, maxval=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('4%')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('23%,,42%')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = conftypes.PercList(none_ok=True)
        t.validate('23%,,42%')

    def test_transform_single(self):
        """Test transform with a single value."""
        self.assertEqual(self.t.transform('1337%'), [1337])

    def test_transform_more(self):
        """Test transform with multiple values."""
        self.assertEqual(self.t.transform('23%,42%,1337%'), [23, 42, 1337])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertEqual(self.t.transform('23%,,42%'), [23, None, 42])


class PercOrIntTests(unittest.TestCase):

    """Test PercOrInt."""

    def setUp(self):
        self.t = conftypes.PercOrInt()

    def test_minint_gt_maxint(self):
        """Test __init__ with a minint bigger than the maxint."""
        with self.assertRaises(ValueError):
            conftypes.PercOrInt(minint=2, maxint=1)

    def test_minperc_gt_maxperc(self):
        """Test __init__ with a minperc bigger than the maxperc."""
        with self.assertRaises(ValueError):
            conftypes.PercOrInt(minperc=2, maxperc=1)

    def test_validate_string(self):
        """Test validate with something which isn't a percentage."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('1337%%')

    def test_validate_perc(self):
        """Test validate with a percentage."""
        self.t.validate('1337%')

    def test_validate_int(self):
        """Test validate with a normal int."""
        self.t.validate('1337')

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.PercOrInt(none_ok=True)
        t.validate('')

    def test_validate_minint_toosmall(self):
        """Test validate with a minint and a too small int."""
        t = conftypes.PercOrInt(minint=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1')

    def test_validate_minint_ok(self):
        """Test validate with a minint and a good int."""
        t = conftypes.PercOrInt(minint=2)
        t.validate('2')

    def test_validate_maxint_toolarge(self):
        """Test validate with a maxint and a too big int."""
        t = conftypes.PercOrInt(maxint=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3')

    def test_validate_maxint_ok(self):
        """Test validate with a maxint and a good int."""
        t = conftypes.PercOrInt(maxint=2)
        t.validate('2')

    def test_validate_int_range_ok(self):
        """Test validate with both min/maxint and a good int."""
        t = conftypes.PercOrInt(minint=2, maxint=3)
        t.validate('2')
        t.validate('3')

    def test_validate_int_range_bad(self):
        """Test validate with both min/maxint and a bad int."""
        t = conftypes.PercOrInt(minint=2, maxint=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('4')

    def test_validate_minperc_toosmall(self):
        """Test validate with a minperc and a too small perc."""
        t = conftypes.PercOrInt(minperc=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')

    def test_validate_minperc_ok(self):
        """Test validate with a minperc and a good perc."""
        t = conftypes.PercOrInt(minperc=2)
        t.validate('2%')

    def test_validate_maxperc_toolarge(self):
        """Test validate with a maxperc and a too big perc."""
        t = conftypes.PercOrInt(maxperc=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3%')

    def test_validate_maxperc_ok(self):
        """Test validate with a maxperc and a good perc."""
        t = conftypes.PercOrInt(maxperc=2)
        t.validate('2%')

    def test_validate_perc_range_ok(self):
        """Test validate with both min/maxperc and a good perc."""
        t = conftypes.PercOrInt(minperc=2, maxperc=3)
        t.validate('2%')
        t.validate('3%')

    def test_validate_perc_range_bad(self):
        """Test validate with both min/maxperc and a bad perc."""
        t = conftypes.PercOrInt(minperc=2, maxperc=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1%')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('4%')

    def test_validate_both_range_int(self):
        """Test validate with both min/maxperc and make sure int is ok."""
        t = conftypes.PercOrInt(minperc=2, maxperc=3)
        t.validate('4')
        t.validate('1')

    def test_validate_both_range_int(self):
        """Test validate with both min/maxint and make sure perc is ok."""
        t = conftypes.PercOrInt(minint=2, maxint=3)
        t.validate('4%')
        t.validate('1%')

    def test_transform_none(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform_perc(self):
        """Test transform with a percentage."""
        self.assertEqual(self.t.transform('1337%'), '1337%')

    def test_transform_int(self):
        """Test transform with an int."""
        self.assertEqual(self.t.transform('1337'), '1337')


class CommandTests(unittest.TestCase):

    """Test Command."""

    def setUp(self):
        self.old_cmdutils = conftypes.cmdutils
        commands = {
            'cmd1': FakeCommand("desc 1"),
            'cmd2': FakeCommand("desc 2"),
        }
        conftypes.cmdutils = FakeCmdUtils(commands)
        self.t = conftypes.Command()

    def tearDown(self):
        conftypes.cmdutils = self.old_cmdutils

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.Command(none_ok=True)
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
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('cmd3')

    def test_validate_invalid_command_args(self):
        """Test validate with an invalid command and arguments."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('cmd3  foo bar')

    def test_transform(self):
        """Make sure transform doesn't alter values."""
        self.assertEqual(self.t.transform('foo bar'), 'foo bar')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_complete(self):
        """Test complete."""
        items = self.t.complete()
        self.assertEqual(len(items), 2)
        self.assertIn(('cmd1', "desc 1"), items)
        self.assertIn(('cmd2', "desc 2"), items)


class ColorSystemTests(unittest.TestCase):

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

    def setUp(self):
        self.t = conftypes.ColorSystem()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.ColorSystem(none_ok=True)
        t.validate('')

    def test_validate_valid(self):
        """Test validate with valid values."""
        for val in self.TESTS:
            self.t.validate(val)

    def test_validate_invalid(self):
        """Test validate with invalid values."""
        for val in self.INVALID:
            with self.assertRaises(conftypes.ValidationError, msg=val):
                self.t.validate(val)

    def test_transform(self):
        """Test transform."""
        for k, v in self.TESTS.items():
            self.assertEqual(self.t.transform(k), v, k)

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))


class QtColorTests(unittest.TestCase):

    """Test QtColor."""

    VALID = ['#123', '#112233', '#111222333', '#111122223333', 'red']
    INVALID = ['#00000G', '#123456789ABCD', '#12', 'foobar', '42']
    INVALID_QT = ['rgb(0, 0, 0)']

    def setUp(self):
        self.t = conftypes.QtColor()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.QtColor(none_ok=True)
        t.validate('')

    def test_validate_valid(self):
        """Test validate with valid values."""
        for v in self.VALID:
            self.t.validate(v)

    def test_validate_invalid(self):
        """Test validate with invalid values."""
        for val in self.INVALID + self.INVALID_QT:
            with self.assertRaises(conftypes.ValidationError, msg=val):
                self.t.validate(val)

    def test_transform(self):
        """Test transform."""
        for v in self.VALID:
            self.assertEqual(self.t.transform(v), QColor(v), v)

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))


class CssColorTests(QtColorTests):

    """Test CssColor."""

    VALID = QtColorTests.VALID + ['-foobar(42)']

    def setUp(self):
        self.t = conftypes.CssColor()

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.CssColor(none_ok=True)
        t.validate('')

    def test_transform(self):
        """Make sure transform doesn't alter the value."""
        for v in self.VALID:
            self.assertEqual(self.t.transform(v), v, v)


class QssColorTests(QtColorTests):

    """Test QssColor."""

    VALID = QtColorTests.VALID + [
        'rgba(255, 255, 255, 255)', 'hsv(359, 255, 255)',
        'hsva(359, 255, 255, 255)', 'hsv(10%, 10%, 10%)',
        'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 white, stop: 0.4 '
        'gray, stop:1 green)',
        'qconicalgradient(cx:0.5, cy:0.5, angle:30, stop:0 white, stop:1 '
        '#00FF00)',
        'qradialgradient(cx:0, cy:0, radius: 1, fx:0.5, fy:0.5, stop:0 '
        'white, stop:1 green)'
    ]
    INVALID = QtColorTests.INVALID + ['rgb(1, 2, 3, 4)', 'foo(1, 2, 3)']
    INVALID_QT = []

    def setUp(self):
        self.t = conftypes.QssColor()

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.QssColor(none_ok=True)
        t.validate('')

    def test_transform(self):
        """Make sure transform doesn't alter the value."""
        for v in self.VALID:
            self.assertEqual(self.t.transform(v), v, v)


class FontTests(unittest.TestCase):

    """Test Font."""

    TESTS = {
        # (style, weight, pointsize, pixelsize, family
        '"Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, -1, -1, 'Foobar Neue'),
        '10pt "Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, 10, None, 'Foobar Neue'),
        '10PT "Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, 10, None, 'Foobar Neue'),
        '10.5pt "Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, 10.5, None, 'Foobar Neue'),
        '10px "Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, None, 10, 'Foobar Neue'),
        '10PX "Foobar Neue"':
            (QFont.StyleNormal, QFont.Normal, None, 10, 'Foobar Neue'),
        'bold "Foobar Neue"':
            (QFont.StyleNormal, QFont.Bold, -1, -1, 'Foobar Neue'),
        'italic "Foobar Neue"':
            (QFont.StyleItalic, QFont.Normal, -1, -1, 'Foobar Neue'),
        'oblique "Foobar Neue"':
            (QFont.StyleOblique, QFont.Normal, -1, -1, 'Foobar Neue'),
        'normal bold "Foobar Neue"':
            (QFont.StyleNormal, QFont.Bold, -1, -1, 'Foobar Neue'),
        'bold italic "Foobar Neue"':
            (QFont.StyleItalic, QFont.Bold, -1, -1, 'Foobar Neue'),
        'bold 10pt "Foobar Neue"':
            (QFont.StyleNormal, QFont.Bold, 10, None, 'Foobar Neue'),
        'italic 10pt "Foobar Neue"':
            (QFont.StyleItalic, QFont.Normal, 10, None, 'Foobar Neue'),
        'oblique 10pt "Foobar Neue"':
            (QFont.StyleOblique, QFont.Normal, 10, None, 'Foobar Neue'),
        'normal bold 10pt "Foobar Neue"':
            (QFont.StyleNormal, QFont.Bold, 10, None, 'Foobar Neue'),
        'bold italic 10pt "Foobar Neue"':
            (QFont.StyleItalic, QFont.Bold, 10, None, 'Foobar Neue'),
    }
    INVALID = ['green "Foobar Neue"', 'italic green "Foobar Neue"',
               'bold bold "Foobar Neue"', 'bold italic "Foobar Neue"'
               'bold', '10pt 20px "Foobar Neue"'
    ]

    def setUp(self):
        self.t = conftypes.Font()
        self.t2 = conftypes.QtFont()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.Font(none_ok=True)
        t2 = conftypes.QtFont(none_ok=True)
        t.validate('')
        t2.validate('')

    def test_validate_valid(self):
        """Test validate with valid values."""
        for val in self.TESTS:
            self.t.validate(val)
            self.t2.validate(val)

    # FIXME
    @unittest.expectedFailure
    def test_validate_invalid(self):
        """Test validate with invalid values."""
        for val in self.INVALID:
            with self.assertRaises(conftypes.ValidationError, msg=val):
                self.t.validate(val)
            with self.assertRaises(conftypes.ValidationError, msg=val):
                self.t2.validate(val)

    # FIXME
    @unittest.expectedFailure
    def test_transform(self):
        """Test transform."""
        for string, desc in self.TESTS.items():
            self.assertEqual(self.t.transform(string), string, string)
            self.assertEqual(Font(self.t2.transform(string)),
                             Font.fromdesc(desc), string)

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))
        self.assertIsNone(self.t2.transform(''))


class RegexTests(unittest.TestCase):

    """Test Regex."""

    def setUp(self):
        self.t = conftypes.Regex()

    def test_validate_empty(self):
        """Test validate with an empty string."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty string and none_ok=True."""
        t = conftypes.Regex(none_ok=True)
        t.validate('')

    def test_validate(self):
        """Test validate with a valid regex."""
        self.t.validate(r'(foo|bar)?baz[fis]h')

    def test_validate_invalid(self):
        """Test validate with an invalid regex."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate(r'(foo|bar))?baz[fis]h')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform_empty(self):
        """Test transform."""
        self.assertEqual(self.t.transform(r'foobar'), re.compile(r'foobar'))


class RegexListTests(unittest.TestCase):

    """Test RegexList."""

    def setUp(self):
        self.t = conftypes.RegexList()

    def test_validate_good(self):
        """Test validate with good values."""
        self.t.validate(r'(foo|bar),[abcd]?,1337{42}')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate(r'(foo|bar),,1337{42}')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = conftypes.RegexList(none_ok=True)
        t.validate(r'(foo|bar),,1337{42}')

    def test_validate_bad(self):
        """Test validate with bad values."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate(r'(foo|bar),((),1337{42}')

    def test_transform_single(self):
        """Test transform with a single value."""
        self.assertEqual(self.t.transform('foo'), [re.compile('foo')])

    def test_transform_more(self):
        """Test transform with multiple values."""
        self.assertEqual(self.t.transform('foo,bar,baz'),
                         [re.compile('foo'), re.compile('bar'),
                          re.compile('baz')])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertEqual(self.t.transform('foo,,bar'),
                         [re.compile('foo'), None, re.compile('bar')])


@mock.patch('qutebrowser.config.conftypes.os.path', autospec=True)
class FileTests(unittest.TestCase):

    """Test File."""

    def setUp(self):
        self.t = conftypes.File()

    def test_validate_empty(self, _os_path):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self, _os_path):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.File(none_ok=True)
        t.validate("")

    def test_validate_does_not_exist(self, os_path):
        """Test validate with a file which does not exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isfile.return_value = False
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('foobar')

    def test_validate_exists_abs(self, os_path):
        """Test validate with a file which does exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isfile.return_value = True
        os_path.isabs.return_value = True
        self.t.validate('foobar')

    def test_validate_exists_not_abs(self, os_path):
        """Test validate with a file which does exist but is not absolute."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isfile.return_value = True
        os_path.isabs.return_value = False
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('foobar')

    def test_validate_expanduser(self, os_path):
        """Test if validate expands the user correctly."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        os_path.isfile.side_effect = lambda path: path == '/home/foo/foobar'
        os_path.isabs.return_value = True
        self.t.validate('~/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform(self, os_path):
        """Test transform."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        self.assertEqual(self.t.transform('~/foobar'), '/home/foo/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform_empty(self, _os_path):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))


@mock.patch('qutebrowser.config.conftypes.os.path', autospec=True)
class DirectoryTests(unittest.TestCase):

    """Test Directory."""

    def setUp(self):
        self.t = conftypes.Directory()

    def test_validate_empty(self, _os_path):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self, _os_path):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Directory(none_ok=True)
        t.validate("")

    def test_validate_does_not_exist(self, os_path):
        """Test validate with a directory which does not exist."""
        os_path.expanduser.side_effect = lambda x: x
        os_path.isdir.return_value = False
        with self.assertRaises(conftypes.ValidationError):
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
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('foobar')

    def test_validate_expanduser(self, os_path):
        """Test if validate expands the user correctly."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        os_path.isdir.side_effect = lambda path: path == '/home/foo/foobar'
        os_path.isabs.return_value = True
        self.t.validate('~/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform(self, os_path):
        """Test transform."""
        os_path.expanduser.side_effect = lambda x: x.replace('~', '/home/foo')
        self.assertEqual(self.t.transform('~/foobar'), '/home/foo/foobar')
        os_path.expanduser.assert_called_once_with('~/foobar')

    def test_transform_empty(self, _os_path):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))


class WebKitByteTests(unittest.TestCase):

    """Test WebKitBytes."""

    def setUp(self):
        self.t = conftypes.WebKitBytes()

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
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('-1')

    def test_validate_int_negative_suffix(self):
        """Test validate with a negative int with suffix."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('-1k')

    def test_validate_int_toobig(self):
        """Test validate with an int which is too big."""
        t = conftypes.WebKitBytes(maxsize=10)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('11')

    def test_validate_int_not_toobig(self):
        """Test validate with an int which is not too big."""
        t = conftypes.WebKitBytes(maxsize=10)
        t.validate('10')

    def test_validate_int_toobig_suffix(self):
        """Test validate with an int which is too big with suffix."""
        t = conftypes.WebKitBytes(maxsize=10)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1k')

    def test_validate_int_invalid_suffix(self):
        """Test validate with an int with an invalid suffix."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('56x')

    def test_validate_int_double_suffix(self):
        """Test validate with an int with a double suffix."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('56kk')

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform_int(self):
        """Test transform with a simple value."""
        self.assertEqual(self.t.transform('10'), 10)

    def test_transform_int_suffix(self):
        """Test transform with a value with suffix."""
        self.assertEqual(self.t.transform('1k'), 1024)


class WebKitBytesListTests(unittest.TestCase):

    """Test WebKitBytesList."""

    def setUp(self):
        self.t = conftypes.WebKitBytesList()

    def test_validate_good(self):
        """Test validate with good values."""
        t = conftypes.WebKitBytesList()
        t.validate('23,56k,1337')

    def test_validate_bad(self):
        """Test validate with bad values."""
        t = conftypes.WebKitBytesList()
        with self.assertRaises(conftypes.ValidationError):
            t.validate('23,56kk,1337')

    def test_validate_maxsize_toolarge(self):
        """Test validate with a maxsize and a too big size."""
        t = conftypes.WebKitBytesList(maxsize=2)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('3k')

    def test_validate_maxsize_ok(self):
        """Test validate with a maxsize and a good size."""
        t = conftypes.WebKitBytesList(maxsize=2)
        t.validate('2')

    def test_validate_empty(self):
        """Test validate with an empty value."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('23,,42')

    def test_validate_empty_none_ok(self):
        """Test validate with an empty value and none_ok=True."""
        t = conftypes.WebKitBytesList(none_ok=True)
        t.validate('23,,42')

    def test_validate_len_tooshort(self):
        """Test validate with a too short length."""
        t = conftypes.WebKitBytesList(length=3)
        with self.assertRaises(conftypes.ValidationError):
            t.validate('1,2')

    def test_validate_len_ok(self):
        """Test validate with a correct length."""
        t = conftypes.WebKitBytesList(length=3)
        t.validate('1,2,3')

    def test_validate_len_tooshort(self):
        """Test validate with a too long length."""
        t = conftypes.WebKitBytesList(length=3)
        with self.assertRaises(conftypes.ValidationError):

            t.validate('1,2,3,4')

    def test_transform_single(self):
        """Test transform with a single value."""
        self.assertEqual(self.t.transform('1k'), [1024])

    def test_transform_more(self):
        """Test transform with multiple values."""
        self.assertEqual(self.t.transform('23,2k,1337'), [23, 2048, 1337])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertEqual(self.t.transform('23,,42'), [23, None, 42])


class ShellCommandTests(unittest.TestCase):

    """Test ShellCommand."""

    def setUp(self):
        self.t = conftypes.ShellCommand()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.ShellCommand(none_ok=True)
        t.validate("")

    def test_validate_simple(self):
        """Test validate with a simple string."""
        self.t.validate('foobar')

    def test_validate_placeholder(self):
        """Test validate with a placeholder."""
        t = conftypes.ShellCommand(placeholder='{}')
        t.validate('foo {} bar')

    def test_validate_placeholder_invalid(self):
        """Test validate with an invalid placeholder."""
        t = conftypes.ShellCommand(placeholder='{}')
        with self.assertRaises(conftypes.ValidationError):
            t.validate('foo{} bar')

    def test_transform_single(self):
        """Test transform with a single word."""
        self.assertEqual(self.t.transform('foobar'), ['foobar'])

    def test_transform_double(self):
        """Test transform with two words."""
        self.assertEqual(self.t.transform('foobar baz'), ['foobar', 'baz'])

    def test_transform_quotes(self):
        """Test transform with a quoted word."""
        self.assertEqual(self.t.transform('foo "bar baz" fish'),
                         ['foo', 'bar baz', 'fish'])

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))


class ProxyTests(unittest.TestCase):

    """Test Proxy."""

    def setUp(self):
        self.t = conftypes.Proxy()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.Proxy(none_ok=True)
        t.validate('')

    def test_validate_system(self):
        """Test validate with system proxy."""
        self.t.validate('system')

    def test_validate_none(self):
        """Test validate with none proxy."""
        self.t.validate('none')

    def test_validate_invalid(self):
        """Test validate with an invalid URL."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate(':')

    def test_validate_scheme(self):
        """Test validate with a URL with wrong scheme."""
        with self.assertRaises(conftypes.ValidationError):
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
        self.assertEqual(self.t.complete(),
                         [('system', "Use the system wide proxy."),
                          ('none', "Don't use any proxy"),
                          ('http://', 'HTTP proxy URL'),
                          ('socks://', 'SOCKS proxy URL')])

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform_system(self):
        """Test transform with system proxy."""
        self.assertIs(self.t.transform('system'), conftypes.SYSTEM_PROXY)

    def test_transform_none(self):
        """Test transform with no proxy."""
        self.assertEqual(NetworkProxy(self.t.transform('none')),
                         NetworkProxy(QNetworkProxy.NoProxy))

    def test_transform_socks(self):
        """Test transform with a socks proxy."""
        proxy = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')
        val = NetworkProxy(self.t.transform('socks://example.com/'))
        self.assertEqual(proxy, val)

    def test_transform_socks5(self):
        """Test transform with a socks5 proxy."""
        proxy = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')
        val = NetworkProxy(self.t.transform('socks5://example.com'))
        self.assertEqual(proxy, val)

    def test_transform_http_port(self):
        """Test transform with a http proxy with set port."""
        proxy = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2342)
        val = NetworkProxy(self.t.transform('socks5://example.com:2342'))
        self.assertEqual(proxy, val)

    def test_transform_socks_user(self):
        """Test transform with a socks proxy with set user."""
        proxy = NetworkProxy(
            QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo')
        val = NetworkProxy(self.t.transform('socks5://foo@example.com'))
        self.assertEqual(proxy, val)

    def test_transform_socks_user_password(self):
        """Test transform with a socks proxy with set user/password."""
        proxy = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0,
                             'foo', 'bar')
        val = NetworkProxy(self.t.transform('socks5://foo:bar@example.com'))
        self.assertEqual(proxy, val)

    def test_transform_socks_user_password_port(self):
        """Test transform with a socks proxy with set port/user/password."""
        proxy = NetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2323,
                             'foo', 'bar')
        val = NetworkProxy(
            self.t.transform('socks5://foo:bar@example.com:2323'))
        self.assertEqual(proxy, val)



class SearchEngineNameTests(unittest.TestCase):

    """Test SearchEngineName."""

    def setUp(self):
        self.t = conftypes.SearchEngineName()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.SearchEngineName(none_ok=True)
        t.validate('')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform(self):
        """Test transform with a value."""
        self.assertEqual(self.t.transform("foobar"), "foobar")


class SearchEngineUrlTests(unittest.TestCase):

    """Test SearchEngineUrl."""

    def setUp(self):
        self.t = conftypes.SearchEngineUrl()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.SearchEngineUrl(none_ok=True)
        t.validate('')

    def test_validate_no_placeholder(self):
        """Test validate with no placeholder."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('foo')

    def test_validate(self):
        """Test validate with a good value."""
        self.t.validate('http://example.com/?q={}')

    def test_validate_invalid_url(self):
        """Test validate with an invalud URL."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate(':{}')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))


    def test_transform(self):
        """Test transform with a value."""
        self.assertEqual(self.t.transform("foobar"), "foobar")


class KeyBindingNameTests(unittest.TestCase):

    """Test KeyBindingName."""

    def setUp(self):
        self.t = conftypes.KeyBindingName()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.KeyBindingName(none_ok=True)
        t.validate('')

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform(self):
        """Test transform with a value."""
        self.assertEqual(self.t.transform("foobar"), "foobar")


class WebSettingsFileTests(unittest.TestCase):

    """Test WebSettingsFile."""

    def setUp(self):
        self.t = conftypes.WebSettingsFile()

    def test_transform_empty(self):
        """Test transform with an empty value."""
        self.assertIsNone(self.t.transform(''))

    def test_transform(self):
        """Test transform with a value."""
        self.assertEqual(self.t.transform("/foo/bar"), QUrl("file:///foo/bar"))


class AutoSearchTests(unittest.TestCase):

    """Test AutoSearch."""

    TESTS = {
        'naive': ['naive', 'NAIVE'] + BoolTests.TESTS[True],
        'dns': ['dns', 'DNS'],
        False: BoolTests.TESTS[False],
    }
    INVALID = ['ddns', 'foo']

    def setUp(self):
        self.t = conftypes.AutoSearch()

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate('')

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        t = conftypes.AutoSearch(none_ok=True)
        t.validate('')

    def test_validate_valid(self):
        """Test validate with valid values."""
        for vallist in self.TESTS.values():
            for val in vallist:
                self.t.validate(val)

    def test_validate_invalid(self):
        """Test validate with invalid values."""
        for val in self.INVALID:
            with self.assertRaises(conftypes.ValidationError):
                self.t.validate(val)

    def test_transform(self):
        """Test transform with all values."""
        for out, inputs in self.TESTS.items():
            for inp in inputs:
                self.assertEqual(self.t.transform(inp), out, inp)

    def test_transform_empty(self):
        """Test transform with none_ok = False and an empty value."""
        self.assertIsNone(self.t.transform(''))


if __name__ == '__main__':
    unittest.main()
