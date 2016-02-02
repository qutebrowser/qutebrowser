# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# Based on the Eric5 helpviewer,
# Copyright (c) 2009 - 2014 Detlev Offenbach <detlev@die-offenbachs.de>
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

"""Base class for custom scheme handlers."""

from PyQt5.QtCore import QObject


class SchemeHandler(QObject):

    """Abstract base class for custom scheme handlers.

    Attributes:
        _win_id: The window ID this scheme handler is associated with.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id

    def createRequest(self, op, request, outgoing_data):
        """Create a new request.

        Args:
             op: Operation op
             req: const QNetworkRequest & req
             outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.
        """
        raise NotImplementedError
