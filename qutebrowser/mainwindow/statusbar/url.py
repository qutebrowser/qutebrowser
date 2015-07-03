# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.browser import webview
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.config import style
from qutebrowser.utils import usertypes


# Note this has entries for success/error/warn from widgets.webview:LoadStatus
UrlType = usertypes.enum('UrlType', ['success', 'error', 'warn', 'hover',
                                     'normal'])


class UrlText(textbase.TextBase):

    """URL displayed in the statusbar.

    Attributes:
        _normal_url: The normal URL to be displayed as a UrlType instance.
        _normal_url_type: The type of the normal URL as a UrlType instance.
        _hover_url: The URL we're currently hovering over.
        _ssl_errors: Whether SSL errors occurred while loading.

    Class attributes:
        _urltype: The URL type to show currently (normal/ok/error/warn/hover).
                  Accessed via the urltype property.

                  For some reason we need to have this as class attribute so
                  pyqtProperty works correctly.
    """

    _urltype = None

    STYLESHEET = """
        QLabel#UrlText[urltype="normal"] {
            {{ color['statusbar.url.fg'] }}
        }

        QLabel#UrlText[urltype="success"] {
            {{ color['statusbar.url.fg.success'] }}
        }

        QLabel#UrlText[urltype="error"] {
            {{ color['statusbar.url.fg.error'] }}
        }

        QLabel#UrlText[urltype="warn"] {
            {{ color['statusbar.url.fg.warn'] }}
        }

        QLabel#UrlText[urltype="hover"] {
            {{ color['statusbar.url.fg.hover'] }}
        }
    """

    def __init__(self, parent=None):
        """Override TextBase.__init__ to elide in the middle by default."""
        super().__init__(parent, Qt.ElideMiddle)
        self.setObjectName(self.__class__.__name__)
        style.set_register_stylesheet(self)
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
        if self._hover_url is not None:
            self.setText(self._hover_url)
            self._urltype = UrlType.hover
        elif self._normal_url is not None:
            self.setText(self._normal_url)
            self._urltype = self._normal_url_type
        else:
            self.setText('')
            self._urltype = UrlType.normal
        self.setStyleSheet(style.get_stylesheet(self.STYLESHEET))

    @pyqtSlot(str)
    def on_load_status_changed(self, status_str):
        """Slot for load_status_changed. Sets URL color accordingly.

        Args:
            status_str: The LoadStatus as string.
        """
        status = webview.LoadStatus[status_str]
        if status in (webview.LoadStatus.success, webview.LoadStatus.error,
                      webview.LoadStatus.warn):
            self._normal_url_type = UrlType[status_str]
        else:
            self._normal_url_type = UrlType.normal
        self._update_url()

    @pyqtSlot(str)
    def set_url(self, s):
        """Setter to be used as a Qt slot.

        Args:
            s: The URL to set as string.
        """
        self._normal_url = s
        self._normal_url_type = UrlType.normal
        self._update_url()

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
            self._hover_url = link
        else:
            self._hover_url = None
        self._update_url()

    @pyqtSlot(int)
    def on_tab_changed(self, tab):
        """Update URL if the tab changed."""
        self._hover_url = None
        self._normal_url = tab.cur_url.toDisplayString()
        self.on_load_status_changed(tab.load_status.name)
        self._update_url()
