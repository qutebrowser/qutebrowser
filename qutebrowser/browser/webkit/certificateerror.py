# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A wrapper over a list of QSslErrors."""

from typing import Optional
from collections.abc import Sequence

from qutebrowser.qt.network import QSslError, QNetworkReply

from qutebrowser.utils import usertypes, utils, debug, jinja, urlutils


class CertificateErrorWrapper(usertypes.AbstractCertificateErrorWrapper):

    """A wrapper over a list of QSslErrors."""

    def __init__(self, reply: QNetworkReply, errors: Sequence[QSslError]) -> None:
        super().__init__()
        self._reply = reply
        self._errors = tuple(errors)  # needs to be hashable
        try:
            self._host_tpl: Optional[urlutils.HostTupleType] = urlutils.host_tuple(reply.url())
        except ValueError:
            self._host_tpl = None

    def __str__(self) -> str:
        return '\n'.join(err.errorString() for err in self._errors)

    def __repr__(self) -> str:
        return utils.get_repr(
            self,
            errors=[debug.qenum_key(QSslError, err.error()) for err in self._errors],
            string=str(self))

    def __hash__(self) -> int:
        return hash((self._host_tpl, self._errors))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CertificateErrorWrapper):
            return NotImplemented
        return self._errors == other._errors and self._host_tpl == other._host_tpl

    def is_overridable(self) -> bool:
        return True

    def defer(self) -> None:
        raise usertypes.UndeferrableError("Never deferrable")

    def accept_certificate(self) -> None:
        super().accept_certificate()
        self._reply.ignoreSslErrors()

    # Not overriding reject_certificate because that's default in QNetworkReply

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
