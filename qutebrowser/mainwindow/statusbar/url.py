# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import enum

from PyQt5.QtCore import (pyqtSlot, pyqtProperty,  # type: ignore[attr-defined]
                          QUrl)

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.config import stylesheet
from qutebrowser.utils import usertypes, urlutils


# Note this has entries for success/error/warn from widgets.webview:LoadStatus
UrlType = enum.Enum('UrlType', ['success', 'success_https', 'error', 'warn',
                                'hover', 'normal'])


class UrlText(textbase.TextBase):

    """URL displayed in the statusbar.

    Attributes:
        _normal_url: The normal URL to be displayed as a UrlType instance.
        _normal_url_type: The type of the normal URL as a UrlType instance.
        _hover_url: The URL we're currently hovering over.
        _ssl_errors: Whether SSL errors occurred while loading.
        _urltype: The URL type to show currently (normal/ok/error/warn/hover).
                  Accessed via the urltype property.
    """

    STYLESHEET = """
        QLabel#UrlText[urltype="normal"] {
            color: {{ conf.colors.statusbar.url.fg }};
        }

        QLabel#UrlText[urltype="success"] {
            color: {{ conf.colors.statusbar.url.success.http.fg }};
        }

        QLabel#UrlText[urltype="success_https"] {
            color: {{ conf.colors.statusbar.url.success.https.fg }};
        }

        QLabel#UrlText[urltype="error"] {
            color: {{ conf.colors.statusbar.url.error.fg }};
        }

        QLabel#UrlText[urltype="warn"] {
            color: {{ conf.colors.statusbar.url.warn.fg }};
        }

        QLabel#UrlText[urltype="hover"] {
            color: {{ conf.colors.statusbar.url.hover.fg }};
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._urltype = None
        self.setObjectName(self.__class__.__name__)
        stylesheet.set_register(self)
        self._hover_url = None
        self._normal_url = None
        self._normal_url_type = UrlType.normal

    @pyqtProperty(str)
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property.

        Return:
            The urltype as a string (!)
        """
        if self._urltype is None:
            return ""
        else:
            return self._urltype.name

    def _update_url(self):
        """Update the displayed URL if the url or the hover url changed."""
        old_urltype = self._urltype
        if self._hover_url is not None:
            self.setText(self._hover_url)
            self._urltype = UrlType.hover
        elif self._normal_url is not None:
            self.setText(self._normal_url)
            self._urltype = self._normal_url_type
        else:
            self.setText('')
            self._urltype = UrlType.normal
        if old_urltype != self._urltype:
            # We can avoid doing an unpolish here because the new style will
            # always override the old one.
            self.style().polish(self)

    @pyqtSlot(usertypes.LoadStatus)
    def on_load_status_changed(self, status):
        """Slot for load_status_changed. Sets URL color accordingly.

        Args:
            status: The usertypes.LoadStatus.
        """
        assert isinstance(status, usertypes.LoadStatus), status
        if status in [usertypes.LoadStatus.success,
                      usertypes.LoadStatus.success_https,
                      usertypes.LoadStatus.error,
                      usertypes.LoadStatus.warn]:
            self._normal_url_type = UrlType[status.name]
        else:
            self._normal_url_type = UrlType.normal
        self._update_url()

    @pyqtSlot(QUrl)
    def set_url(self, url):
        """Setter to be used as a Qt slot.

        Args:
            url: The URL to set as QUrl, or None.
        """
        if url is None:
            self._normal_url = None
        elif not url.isValid():
            self._normal_url = "Invalid URL!"
        else:
            self._normal_url = urlutils.safe_display_string(url)
        self._normal_url_type = UrlType.normal
        self._update_url()

    @pyqtSlot(str)
    def set_hover_url(self, link):
        """Setter to be used as a Qt slot.

        Saves old shown URL in self._old_url and restores it later if a link is
        "un-hovered" when it gets called with empty parameters.

        Args:
            link: The link which was hovered (string)
        """
        if link:
            qurl = QUrl(link)
            if qurl.isValid():
                self._hover_url = urlutils.safe_display_string(qurl)
            else:
                self._hover_url = '(invalid URL!) {}'.format(link)
        else:
            self._hover_url = None
        self._update_url()

    def on_tab_changed(self, tab):
        """Update URL if the tab changed."""
        self._hover_url = None
        if tab.url().isValid():
            self._normal_url = urlutils.safe_display_string(tab.url())
        else:
            self._normal_url = ''
        self.on_load_status_changed(tab.load_status())
        self._update_url()
