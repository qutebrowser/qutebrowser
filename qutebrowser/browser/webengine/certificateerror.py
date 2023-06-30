# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrapper over a QWebEngineCertificateError."""

from typing import Any

from qutebrowser.qt import machinery
from qutebrowser.qt.core import QUrl
from qutebrowser.qt.webenginecore import QWebEngineCertificateError

from qutebrowser.utils import usertypes, utils, debug


class CertificateErrorWrapper(usertypes.AbstractCertificateErrorWrapper):

    """A wrapper over a QWebEngineCertificateError.

    Support both Qt 5 and 6.
    """

    def __init__(self, error: QWebEngineCertificateError) -> None:
        super().__init__()
        self._error = error
        self.ignore = False

    def __str__(self) -> str:
        if machinery.IS_QT5:
            return self._error.errorDescription()
        else:
            return self._error.description()

    def _type(self) -> Any:  # QWebEngineCertificateError.Type or .Error
        if machinery.IS_QT5:
            return self._error.error()
        else:
            return self._error.type()

    def reject_certificate(self) -> None:
        super().reject_certificate()
        self._error.rejectCertificate()

    def accept_certificate(self) -> None:
        super().accept_certificate()
        if machinery.IS_QT5:
            self._error.ignoreCertificateError()
        else:
            self._error.acceptCertificate()

    def __repr__(self) -> str:
        return utils.get_repr(
            self,
            error=debug.qenum_key(QWebEngineCertificateError, self._type()),
            string=str(self))

    def url(self) -> QUrl:
        return self._error.url()

    def is_overridable(self) -> bool:
        return self._error.isOverridable()

    def defer(self) -> None:
        # WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2022-April/044585.html
        # (PyQt 5.15.6, 6.2.3, 6.3.0)
        raise usertypes.UndeferrableError("PyQt bug")
