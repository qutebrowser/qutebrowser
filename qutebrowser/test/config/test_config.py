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

# pylint: disable=protected-access

"""Tests for qutebrowser.config.config."""

import unittest
import configparser

from PyQt5.QtGui import QColor

from qutebrowser.config import config, configexc


class ConfigParserTests(unittest.TestCase):

    """Test reading of ConfigParser."""

    def setUp(self):
        self.cp = configparser.ConfigParser(interpolation=None,
                                            comment_prefixes='#')
        self.cp.optionxform = lambda opt: opt  # be case-insensitive
        self.cfg = config.ConfigManager(None, None)

    def test_simple(self):
        """Test a simple option which is not transformed."""
        self.cp.read_dict({'general': {'ignore-case': 'false'}})
        self.cfg._from_cp(self.cp)
        self.assertFalse(self.cfg.get('general', 'ignore-case'))

    def test_transformed_section_old(self):
        """Test a transformed section with the old name."""
        self.cp.read_dict({'permissions': {'allow-plugins': 'true'}})
        self.cfg._from_cp(self.cp)
        self.assertTrue(self.cfg.get('content', 'allow-plugins'))

    def test_transformed_section_new(self):
        """Test a transformed section with the new name."""
        self.cp.read_dict({'content': {'allow-plugins': 'true'}})
        self.cfg._from_cp(self.cp)
        self.assertTrue(self.cfg.get('content', 'allow-plugins'))

    def test_transformed_option_old(self):
        """Test a transformed option with the old name."""
        self.cp.read_dict({'colors': {'tab.fg.odd': 'pink'}})
        self.cfg._from_cp(self.cp)
        self.assertEqual(self.cfg.get('colors', 'tabs.fg.odd').name(),
                         QColor('pink').name())

    def test_transformed_option_new(self):
        """Test a transformed section with the new name."""
        self.cp.read_dict({'colors': {'tabs.fg.odd': 'pink'}})
        self.cfg._from_cp(self.cp)
        self.assertEqual(self.cfg.get('colors', 'tabs.fg.odd').name(),
                         QColor('pink').name())

    def test_invalid_value(self):
        """Test setting an invalid value."""
        self.cp.read_dict({'general': {'ignore-case': 'invalid'}})
        self.cfg._from_cp(self.cp)
        with self.assertRaises(configexc.ValidationError):
            self.cfg._validate_all()

    def test_invalid_value_interpolated(self):
        """Test setting an invalid interpolated value."""
        self.cp.read_dict({'general': {'ignore-case': 'smart',
                                       'wrap-search': '${ignore-case}'}})
        self.cfg._from_cp(self.cp)
        with self.assertRaises(configexc.ValidationError):
            self.cfg._validate_all()

    def test_interpolation(self):
        """Test setting an interpolated value."""
        self.cp.read_dict({'general': {'ignore-case': 'false',
                                       'wrap-search': '${ignore-case}'}})
        self.cfg._from_cp(self.cp)
        self.assertFalse(self.cfg.get('general', 'ignore-case'))
        self.assertFalse(self.cfg.get('general', 'wrap-search'))

    def test_interpolation_cross_section(self):
        """Test setting an interpolated value from another section."""
        self.cp.read_dict(
            {
                'general': {'ignore-case': '${network:do-not-track}'},
                'network': {'do-not-track': 'false'},
            }
        )
        self.cfg._from_cp(self.cp)
        self.assertFalse(self.cfg.get('general', 'ignore-case'))
        self.assertFalse(self.cfg.get('network', 'do-not-track'))

    def test_invalid_interpolation(self):
        """Test an invalid interpolation."""
        self.cp.read_dict({'general': {'ignore-case': '${foo}'}})
        self.cfg._from_cp(self.cp)
        with self.assertRaises(configparser.InterpolationError):
            self.cfg._validate_all()

    def test_invalid_interpolation_syntax(self):
        """Test an invalid interpolation syntax."""
        self.cp.read_dict({'general': {'ignore-case': '${'}})
        with self.assertRaises(configexc.InterpolationSyntaxError):
            self.cfg._from_cp(self.cp)

    def test_invalid_section(self):
        """Test an invalid section."""
        self.cp.read_dict({'foo': {'bar': 'baz'}})
        with self.assertRaises(configexc.NoSectionError):
            self.cfg._from_cp(self.cp)

    def test_invalid_option(self):
        """Test an invalid option."""
        self.cp.read_dict({'general': {'bar': 'baz'}})
        with self.assertRaises(configexc.NoOptionError):
            self.cfg._from_cp(self.cp)


if __name__ == '__main__':
    unittest.main()
