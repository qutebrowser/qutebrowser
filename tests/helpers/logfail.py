# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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

        if record.levelno in (logger.level, root_logger.level):
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
