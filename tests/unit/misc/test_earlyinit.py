# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
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

"""Test qutebrowser.misc.earlyinit."""

import os
import sys
import types
import logging
import pkg_resources

import pytest

from qutebrowser.misc import earlyinit


@pytest.mark.parametrize('attr', ['stderr', '__stderr__'])
def test_init_faulthandler_stderr_none(monkeypatch, attr):
    """Make sure init_faulthandler works when sys.stderr/__stderr__ is None."""
    monkeypatch.setattr(sys, attr, None)
    earlyinit.init_faulthandler()


class TestFixHarfbuzz:

    @pytest.fixture(autouse=True)
    def clear_harfbuzz(self):
        """Clear QT_HARFBUZZ before/after tests."""
        old_harfbuzz = os.environ.pop('QT_HARFBUZZ', None)
        yield
        if old_harfbuzz is None:
            os.environ.pop('QT_HARFBUZZ', None)
        else:
            os.environ['QT_HARFBUZZ'] = old_harfbuzz

    @pytest.fixture
    def args(self):
        """Get a fake argparse namespace."""
        return types.SimpleNamespace(harfbuzz='auto')

    @pytest.mark.parametrize('harfbuzz, qt_version, platform, expected', [
        ('auto', '5.2.1', 'linux', 'old'),
        ('auto', '5.3.0', 'linux', 'new'),
        ('auto', '5.3.2', 'linux', 'old'),
        ('auto', '5.4.0', 'linux', None),

        ('auto', '5.2.1', 'windows', None),

        ('old', '5.3.0', 'linux', 'old'),
        ('old', '5.4.0', 'linux', 'old'),

        ('new', '5.2.1', 'linux', 'new'),
        ('new', '5.3.2', 'linux', 'new'),
        ('new', '5.4.0', 'linux', 'new'),
    ])
    def test_fix_harfbuzz(self, clear_harfbuzz, args, monkeypatch, caplog,
                          harfbuzz, qt_version, platform, expected):
        """Check the QT_HARFBUZZ env var."""
        args.harfbuzz = harfbuzz
        monkeypatch.setattr(earlyinit, '_qt_version',
                            lambda: pkg_resources.parse_version(qt_version))
        monkeypatch.setattr(earlyinit.sys, 'platform', platform)

        with caplog.at_level(logging.WARNING):
            # Because QtWidgets is already imported
            earlyinit.fix_harfbuzz(args)

        assert os.environ.get('QT_HARFBUZZ', None) == expected

    @pytest.mark.parametrize('frozen, level', [
        (True, logging.DEBUG),
        (False, logging.WARNING),
    ])
    def test_widgets_warning(self, args, monkeypatch, caplog, frozen, level):
        """Make sure fix_harfbuzz warns when QtWidgets is imported."""
        # Make sure QtWidgets is in sys.modules
        from PyQt5 import QtWidgets  # pylint: disable=unused-variable
        if frozen:
            monkeypatch.setattr(earlyinit.sys, 'frozen', True, raising=False)
        else:
            monkeypatch.delattr(earlyinit.sys, 'frozen', raising=False)

        with caplog.at_level(level):
            earlyinit.fix_harfbuzz(args)

        record = caplog.records[0]
        assert record.levelno == level
        msg = "Harfbuzz fix attempted but QtWidgets is already imported!"
        assert record.message == msg

    def test_no_warning(self, args, monkeypatch):
        """Without QtWidgets in sys.modules, no warning should be shown."""
        monkeypatch.setattr(earlyinit.sys, 'modules', {})
        earlyinit.fix_harfbuzz(args)
