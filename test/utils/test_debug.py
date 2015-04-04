# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.debug."""

import re
import time
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyle, QFrame
import pytest

from qutebrowser.utils import debug


class TestQEnumKey:

    """Tests for qenum_key."""

    def test_no_metaobj(self):
        """Test with an enum with no metaobject."""
        with pytest.raises(AttributeError):
            # Make sure it doesn't have a meta object
            # pylint: disable=pointless-statement,no-member
            QStyle.PrimitiveElement.staticMetaObject
        key = debug.qenum_key(QStyle, QStyle.PE_PanelButtonCommand)
        assert key == 'PE_PanelButtonCommand'

    def test_metaobj(self):
        """Test with an enum with metaobject."""
        # pylint: disable=pointless-statement
        QFrame.staticMetaObject  # make sure it has a metaobject
        key = debug.qenum_key(QFrame, QFrame.Sunken)
        assert key == 'Sunken'

    def test_add_base(self):
        """Test with add_base=True."""
        key = debug.qenum_key(QFrame, QFrame.Sunken, add_base=True)
        assert key == 'QFrame.Sunken'

    def test_int_noklass(self):
        """Test passing an int without explicit klass given."""
        with pytest.raises(TypeError):
            debug.qenum_key(QFrame, 42)

    def test_int(self):
        """Test passing an int with explicit klass given."""
        key = debug.qenum_key(QFrame, 0x0030, klass=QFrame.Shadow)
        assert key == 'Sunken'

    def test_unknown(self):
        """Test passing an unknown value."""
        key = debug.qenum_key(QFrame, 0x1337, klass=QFrame.Shadow)
        assert key == '0x1337'

    def test_reconverted(self):
        """Test passing a flag value which was re-converted to an enum."""
        # FIXME maybe this should return the right thing anyways?
        debug.qenum_key(Qt, Qt.Alignment(int(Qt.AlignLeft)))


class TestQFlagsKey:

    """Tests for qflags_key()."""

    fail_issue42 = pytest.mark.xfail(
        reason='https://github.com/The-Compiler/qutebrowser/issues/42')

    @fail_issue42
    def test_single(self):
        """Test with single value."""
        flags = debug.qflags_key(Qt, Qt.AlignTop)
        assert flags == 'AlignTop'

    @fail_issue42
    def test_multiple(self):
        """Test with multiple values."""
        flags = debug.qflags_key(Qt, Qt.AlignLeft | Qt.AlignTop)
        assert flags == 'AlignLeft|AlignTop'

    def test_combined(self):
        """Test with a combined value."""
        flags = debug.qflags_key(Qt, Qt.AlignCenter)
        assert flags == 'AlignHCenter|AlignVCenter'

    @fail_issue42
    def test_add_base(self):
        """Test with add_base=True."""
        flags = debug.qflags_key(Qt, Qt.AlignTop, add_base=True)
        assert flags == 'Qt.AlignTop'

    def test_int_noklass(self):
        """Test passing an int without explicit klass given."""
        with pytest.raises(TypeError):
            debug.qflags_key(Qt, 42)

    @fail_issue42
    def test_int(self):
        """Test passing an int with explicit klass given."""
        flags = debug.qflags_key(Qt, 0x0021, klass=Qt.Alignment)
        assert flags == 'AlignLeft|AlignTop'

    def test_unknown(self):
        """Test passing an unknown value."""
        flags = debug.qflags_key(Qt, 0x1100, klass=Qt.Alignment)
        assert flags == '0x0100|0x1000'


class TestDebug:

    """Test signal debug output functions."""

    @pytest.fixture
    def signal(self, stubs):
        return stubs.FakeSignal()

    def test_signal_name(self, signal):
        """Test signal_name()."""
        assert debug.signal_name(signal) == 'fake'

    def test_dbg_signal(self, signal):
        """Test dbg_signal()."""
        assert debug.dbg_signal(signal, [23, 42]) == 'fake(23, 42)'


    def test_dbg_signal_eliding(self, signal):
        """Test eliding in dbg_signal()."""
        assert debug.dbg_signal(signal, ['x' * 201]) == \
               "fake('{}\u2026)".format('x' * 198)

    def test_dbg_signal_newline(self, signal):
        """Test dbg_signal() with a newline."""
        assert debug.dbg_signal(signal, ['foo\nbar']) == r"fake('foo\nbar')"


class TestLogTime:

    """Test log_time."""

    def test_log_time(self, caplog):
        """Test if log_time logs properly."""
        logger = logging.getLogger('qt-tests')
        with caplog.atLevel(logging.DEBUG, logger.name):
            with debug.log_time(logger, action='foobar'):
                time.sleep(0.1)
            assert len(caplog.records()) == 1
            pattern = re.compile(r'^Foobar took ([\d.]*) seconds\.$')
            match = pattern.match(caplog.records()[0].msg)
            assert match
            duration = float(match.group(1))
            assert 0.09 <= duration <= 0.11