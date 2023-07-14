# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.


"""Tests for qutebrowser.utils.qtlog."""

import dataclasses
import logging

import pytest

from qutebrowser import qutebrowser
from qutebrowser.utils import qtlog

from qutebrowser.qt import core as qtcore


class TestQtMessageHandler:

    @dataclasses.dataclass
    class Context:

        """Fake QMessageLogContext."""

        function: str = None
        category: str = None
        file: str = None
        line: int = None

    @pytest.fixture(autouse=True)
    def init_args(self):
        parser = qutebrowser.get_argparser()
        args = parser.parse_args([])
        qtlog.init(args)

    def test_empty_message(self, caplog):
        """Make sure there's no crash with an empty message."""
        qtlog.qt_message_handler(qtcore.QtMsgType.QtDebugMsg, self.Context(), "")
        assert caplog.messages == ["Logged empty message!"]


class TestHideQtWarning:

    """Tests for hide_qt_warning/QtWarningFilter."""

    @pytest.fixture
    def qt_logger(self):
        return logging.getLogger('qt-tests')

    def test_unfiltered(self, qt_logger, caplog):
        with qtlog.hide_qt_warning("World", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                qt_logger.warning("Hello World")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == 'WARNING'
        assert record.message == "Hello World"

    @pytest.mark.parametrize('line', [
        "Hello",  # exact match
        "Hello World",  # match at start of line
        "  Hello World  ",  # match with spaces
    ])
    def test_filtered(self, qt_logger, caplog, line):
        with qtlog.hide_qt_warning("Hello", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                qt_logger.warning(line)
        assert not caplog.records
