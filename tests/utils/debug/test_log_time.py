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

"""Tests for qutebrowser.utils.debug.log_time."""

import logging
import re
import time

from qutebrowser.utils import debug


def test_log_time(caplog):
    """Test if log_time logs properly."""
    logger_name = 'qt-tests'

    with caplog.atLevel(logging.DEBUG, logger=logger_name):
        with debug.log_time(logging.getLogger(logger_name), action='foobar'):
            time.sleep(0.1)

        records = caplog.records()
        assert len(records) == 1

        pattern = re.compile(r'^Foobar took ([\d.]*) seconds\.$')
        match = pattern.match(records[0].msg)
        assert match

        duration = float(match.group(1))
        assert 0.08 <= duration <= 0.20
