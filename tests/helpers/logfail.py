# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Logging handling for the tests."""

import logging

import pytest


class LogFailHandler(logging.Handler):

    """A logging handler which makes tests fail on unexpected messages."""

    def __init__(self, level=logging.NOTSET, min_level=logging.WARNING):
        self._min_level = min_level
        super().__init__(level)

    def emit(self, record):
        logger = logging.getLogger(record.name)
        root_logger = logging.getLogger()

        if logger.name == 'messagemock':
            return

        if (logger.level == record.levelno or
                root_logger.level == record.levelno):
            # caplog.at_level(...) was used with the level of this message,
            # i.e.  it was expected.
            return
        if record.levelno < self._min_level:
            return
        pytest.fail("Got logging message on logger {} with level {}: "
                    "{}!".format(record.name, record.levelname,
                                 record.getMessage()))


@pytest.fixture(scope='session', autouse=True)
def fail_on_logging():
    handler = LogFailHandler()
    logging.getLogger().addHandler(handler)
    yield
    logging.getLogger().removeHandler(handler)
    handler.close()
