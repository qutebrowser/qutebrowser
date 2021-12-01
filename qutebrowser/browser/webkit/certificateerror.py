# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""A wrapper over a list of QSslErrors."""

from typing import Sequence

from PyQt5.QtNetwork import QSslError

from qutebrowser.utils import usertypes, utils, debug, jinja


class CertificateErrorWrapper(usertypes.AbstractCertificateErrorWrapper):

    """A wrapper over a list of QSslErrors."""

    def __init__(self, errors: Sequence[QSslError]) -> None:
        self._errors = tuple(errors)  # needs to be hashable

    def __str__(self) -> str:
        return '\n'.join(err.errorString() for err in self._errors)

    def __repr__(self) -> str:
        return utils.get_repr(
            self,
            errors=[debug.qenum_key(QSslError, err.error()) for err in self._errors],
            string=str(self))

    def __hash__(self) -> int:
        return hash(self._errors)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CertificateErrorWrapper):
            return NotImplemented
        return self._errors == other._errors

    def is_overridable(self) -> bool:
        return True

    def html(self):
        if len(self._errors) == 1:
            return super().html()

        template = jinja.environment.from_string("""
            <ul>
            {% for err in errors %}
                <li>{{err.errorString()}}</li>
            {% endfor %}
            </ul>
        """.strip())
        return template.render(errors=self._errors)
