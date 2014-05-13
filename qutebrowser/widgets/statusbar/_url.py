# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""URL displayed in the statusbar."""

from PyQt5.QtCore import pyqtSlot, pyqtProperty, Qt

from qutebrowser.widgets.statusbar._textbase import TextBase
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet
from qutebrowser.utils.url import urlstring


class Url(TextBase):

    """URL displayed in the statusbar.

    Class attributes:
        STYLESHEET: The stylesheet template.

    Attributes:
        _old_url: The URL displayed before the hover URL.
        _old_urltype: The type of the URL displayed before the hover URL.
        _ssl_errors: Whether SSL errors occured while loading.

    Class attributes:
        _urltype: The current URL type. One of normal/ok/error/warn/hover.
                  Accessed via the urltype property.

                  For some reason we need to have this as class attribute so
                  pyqtProperty works correctly.
    """

    _urltype = None

    STYLESHEET = """
        QLabel#_Url[urltype="normal"] {{
            {color[statusbar.url.fg]}
        }}

        QLabel#_Url[urltype="success"] {{
            {color[statusbar.url.fg.success]}
        }}

        QLabel#_Url[urltype="error"] {{
            {color[statusbar.url.fg.error]}
        }}

        QLabel#_Url[urltype="warn"] {{
            {color[statusbar.url.fg.warn]}
        }}

        QLabel#_Url[urltype="hover"] {{
            {color[statusbar.url.fg.hover]}
        }}
    """

    def __init__(self, bar, elidemode=Qt.ElideMiddle):
        """Override TextBase::__init__ to elide in the middle by default.

        Args:
            bar: The statusbar (parent) object.
            elidemode: How to elide the text.
        """
        super().__init__(bar, elidemode)
        self.setObjectName(self.__class__.__name__)
        set_register_stylesheet(self)
        self._old_urltype = None
        self._old_url = None
        self._ssl_errors = False

    @pyqtProperty(str)
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._urltype

    @urltype.setter
    def urltype(self, val):
        """Setter for self.urltype, so it can be used as Qt property."""
        self._urltype = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    @pyqtSlot()
    def on_loading_started(self):
        """Slot to clear SSL errors when loading started."""
        self._ssl_errors = False

    @pyqtSlot('QNetworkReply*', 'QList<QSslError>')
    def on_ssl_errors(self, _reply, _errors):
        """Set a flag to get a warning when there were SSL errors."""
        self._ssl_errors = True

    @pyqtSlot(bool)
    def on_loading_finished(self, ok):
        """Slot for cur_loading_finished. Colors the URL according to ok.

        Args:
            ok: Whether loading finished successfully (True) or not (False).
        """
        if ok and not self._ssl_errors:
            self.urltype = 'success'
        elif ok:
            self.urltype = 'warn'
        else:
            self.urltype = 'error'

    @pyqtSlot(str)
    def set_url(self, s):
        """Setter to be used as a Qt slot.

        Args:
            s: The URL to set.
        """
        self.setText(urlstring(s))
        self.urltype = 'normal'

    @pyqtSlot(str, str, str)
    def set_hover_url(self, link, _title, _text):
        """Setter to be used as a Qt slot.

        Saves old shown URL in self._old_url and restores it later if a link is
        "un-hovered" when it gets called with empty parameters.

        Args:
            link: The link which was hovered (string)
            _title: The title of the hovered link (string)
            _text: The text of the hovered link (string)
        """
        if link:
            if self._old_url is None:
                self._old_url = self.text()
            if self._old_urltype is None:
                self._old_urltype = self._urltype
            self.urltype = 'hover'
            self.setText(link)
        else:
            self.setText(self._old_url)
            self.urltype = self._old_urltype
            self._old_url = None
            self._old_urltype = None
