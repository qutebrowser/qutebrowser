# Copyright 2014-2023 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Loggers and utilities related to Qt logging."""

import contextlib
from typing import Iterator, Optional, Callable, cast

from qutebrowser.qt import core as qtcore, machinery


@qtcore.pyqtSlot()
def shutdown_log() -> None:
    qtcore.qInstallMessageHandler(None)


@contextlib.contextmanager
def disable_qt_msghandler() -> Iterator[None]:
    """Contextmanager which temporarily disables the Qt message handler."""
    old_handler = qtcore.qInstallMessageHandler(None)
    if machinery.IS_QT6:
        # cast str to Optional[str] to be compatible with PyQt6 type hints for
        # qInstallMessageHandler
        old_handler = cast(
            Optional[
                Callable[
                    [qtcore.QtMsgType, qtcore.QMessageLogContext, Optional[str]],
                    None
                ]
            ],
            old_handler,
        )

    try:
        yield
    finally:
        qtcore.qInstallMessageHandler(old_handler)
