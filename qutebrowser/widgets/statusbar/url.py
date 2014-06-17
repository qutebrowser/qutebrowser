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

from qutebrowser.widgets.webview import LoadStatus
from qutebrowser.widgets.statusbar.textbase import TextBase
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet


class Url(TextBase):

    """URL displayed in the statusbar.

    Class attributes:
        STYLESHEET: The stylesheet template.

    Attributes:
        normal_url: The normal URL to be displayed.
        normal_url_type: The type of the normal URL.
        hover_url: The URL we're currently hovering over.
        _ssl_errors: Whether SSL errors occured while loading.

    Class attributes:
        _urltype: The URL type to show currently (normal/ok/error/warn/hover).
                  Accessed via the urltype property.

                  For some reason we need to have this as class attribute so
                  pyqtProperty works correctly.
    """

    _urltype = None

    STYLESHEET = """
        QLabel#Url[urltype="normal"] {{
            {color[statusbar.url.fg]}
        }}

        QLabel#Url[urltype="success"] {{
            {color[statusbar.url.fg.success]}
        }}

        QLabel#Url[urltype="error"] {{
            {color[statusbar.url.fg.error]}
        }}

        QLabel#Url[urltype="warn"] {{
            {color[statusbar.url.fg.warn]}
        }}

        QLabel#Url[urltype="hover"] {{
            {color[statusbar.url.fg.hover]}
        }}
    """

    def __init__(self, parent=None):
        """Override TextBase.__init__ to elide in the middle by default."""
        super().__init__(parent, Qt.ElideMiddle)
        self.setObjectName(self.__class__.__name__)
        set_register_stylesheet(self)
        self._hover_url = None
        self._normal_url = None
        self._normal_url_type = 'normal'

    @pyqtProperty(str)
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._urltype

    @urltype.setter
    def urltype(self, val):
        """Setter for self.urltype to update stylesheets after it is set."""
        self._urltype = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    @property
    def hover_url(self):
        """Getter so we can define a setter."""
        return self._hover_url

    @hover_url.setter
    def hover_url(self, val):
        """Setter to update displayed URL when hover_url was set."""
        self._hover_url = val
        self._update_url()

    @property
    def normal_url(self):
        """Getter so we can define a setter."""
        return self._normal_url

    @normal_url.setter
    def normal_url(self, val):
        """Setter to update displayed URL when normal_url was set."""
        self._normal_url = val
        self._update_url()

    @property
    def normal_url_type(self):
        """Getter so we can define a setter."""
        return self._normal_url_type

    @normal_url_type.setter
    def normal_url_type(self, val):
        """Setter to update displayed URL when normal_url_type was set."""
        self._normal_url_type = val
        self._update_url()

    def _update_url(self):
        """Update the displayed URL if the url or the hover url changed."""
        if self.hover_url is not None:
            self.setText(self.hover_url)
            self.urltype = 'hover'
        elif self.normal_url is not None:
            self.setText(self.normal_url)
            self.urltype = self.normal_url_type
        else:
            self.setText('')
            self.urltype = 'normal'

    @pyqtSlot(str)
    def on_load_status_changed(self, status):
        """Slot for load_status_changed. Sets URL color accordingly.

        Args:
            status: The LoadStatus as string.
        """
        if status in ('success', 'error', 'warn'):
            self.normal_url_type = status
        else:
            self.normal_url_type = 'normal'

    @pyqtSlot(str)
    def set_url(self, s):
        """Setter to be used as a Qt slot.

        Args:
            s: The URL to set as string.
        """
        self.normal_url = s
        self.normal_url_type = 'normal'

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
            self.hover_url = link
        else:
            self.hover_url = None

    @pyqtSlot(int)
    def on_tab_changed(self, tab):
        """Update URL if the tab changed."""
        self.hover_url = None
        self.normal_url = tab.url_text
        status = LoadStatus[tab.load_status]
        if status in ('success', 'error', 'warn'):
            self.normal_url_type = status
        else:
            self.normal_url_type = 'normal'
