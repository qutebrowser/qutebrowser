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

import qutebrowser.config.conftypes as conftypes


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
        """Test transform with none_ok = False and an empty value."""
        self.assertEqual(self.t.transform(""), "")

    def test_transform_empty_none_ok(self):
        """Test transform with none_ok = True and an empty value."""
        t = conftypes.BaseType(none_ok=True)
        self.assertIsNone(t.transform(""))

    def test_validate_not_implemented(self):
        """Test validate without valid_values set."""
        with self.assertRaises(NotImplementedError):
            self.t.validate("foo")

    def test_validate_none_ok(self):
        """Test validate with none_ok = True."""
        t = conftypes.BaseType(none_ok=True)
        t.validate("")

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

    def test_validate_empty(self):
        """Test validate with empty string and none_ok = False."""
        self.t = conftypes.String()
        self.t.validate("")

    def test_validate_empty_none_ok(self):
        """Test validate with empty string and none_ok = True."""
        self.t = conftypes.String(none_ok=True)
        self.t.validate("")

    def test_validate(self):
        """Test validate with some random string."""
        self.t = conftypes.String()
        self.t.validate("Hello World! :-)")

    def test_validate_forbidden(self):
        """Test validate with forbidden chars."""
        self.t = conftypes.String(forbidden='xyz')
        self.t.validate("foobar")
        self.t.validate("foXbar")
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate("foybar")
        with self.assertRaises(conftypes.ValidationError):
            self.t.validate("foxbar")


if __name__ == '__main__':
    unittest.main()
