# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrapper over a QSslError."""


from PyQt5.QtNetwork import QSslError

from qutebrowser.utils import usertypes, utils, debug


class CertificateErrorWrapper(usertypes.AbstractCertificateErrorWrapper):

    """A wrapper over a QSslError."""

    def __str__(self):
        return self._error.errorString()

    def __repr__(self):
        return utils.get_repr(
            self, error=debug.qenum_key(QSslError, self._error.error()),
            string=str(self))

    def __hash__(self):
        try:
            # Qt >= 5.4
            return hash(self._error)
        except TypeError:
            return hash((self._error.certificate().toDer(),
                         self._error.error()))

    def __eq__(self, other):
        return self._error == other._error  # pylint: disable=protected-access

    def is_overridable(self):
        return True
