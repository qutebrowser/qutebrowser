# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""URL displayed in the statusbar."""

import enum

from qutebrowser.mainwindow.statusbar.item import StatusBarItem
from qutebrowser.qt.core import pyqtSlot, pyqtProperty, QUrl

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.config import stylesheet
from qutebrowser.utils import usertypes, urlutils


class UrlType(enum.Enum):

    """The type/color of the URL being shown.

    Note this has entries for success/error/warn from widgets.webview:LoadStatus.
    """

    success = enum.auto()
    success_https = enum.auto()
    error = enum.auto()
    warn = enum.auto()
    hover = enum.auto()
    normal = enum.auto()


class UrlTextWidget(textbase.TextBaseWidget):

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
        QLabel#UrlTextWidget[urltype="normal"] {
            color: {{ conf.colors.statusbar.url.fg }};
        }

        QLabel#UrlTextWidget[urltype="success"] {
            color: {{ conf.colors.statusbar.url.success.http.fg }};
        }

        QLabel#UrlTextWidget[urltype="success_https"] {
            color: {{ conf.colors.statusbar.url.success.https.fg }};
        }

        QLabel#UrlTextWidget[urltype="error"] {
            color: {{ conf.colors.statusbar.url.error.fg }};
        }

        QLabel#UrlTextWidget[urltype="warn"] {
            color: {{ conf.colors.statusbar.url.warn.fg }};
        }

        QLabel#UrlTextWidget[urltype="hover"] {
            color: {{ conf.colors.statusbar.url.hover.fg }};
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._urltype = None

    @pyqtProperty(str)  # type: ignore[type-var]
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property.

        Return:
            The urltype as a string (!)
        """
        if self._urltype is None:
            return ""
        else:
            return self._urltype.name


class UrlText(StatusBarItem):
    def __init__(self, widget: UrlTextWidget):
        super().__init__(widget)
        self.widget.setObjectName(self.widget.__class__.__name__)
        stylesheet.set_register(self.widget)
        self._hover_url = None
        self._normal_url = None
        self._normal_url_type = UrlType.normal

    def on_tab_changed(self, tab):
        """Update URL if the tab changed."""
        self._hover_url = None
        if tab.url().isValid():
            self._normal_url = urlutils.safe_display_string(tab.url())
        else:
            self._normal_url = ''
        self.on_load_status_changed(tab.load_status())
        self._update_url()

    def set_url(self, url: QUrl):
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

    def set_hover_url(self, link: str):
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

    def on_load_status_changed(self, status: usertypes.LoadStatus):
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

    def _update_url(self):
        """Update the displayed URL if the url or the hover url changed."""
        old_urltype = self.widget._urltype
        if self._hover_url is not None:
            self.widget.setText(self._hover_url)
            self.widget._urltype = UrlType.hover
        elif self._normal_url is not None:
            self.widget.setText(self._normal_url)
            self.widget._urltype = self._normal_url_type
        else:
            self.widget.setText('')
            self.widget._urltype = UrlType.normal
        if old_urltype != self.widget._urltype:
            # We can avoid doing an unpolish here because the new style will
            # always override the old one.
            style = self.widget.style()
            assert style is not None
            style.polish(self.widget)
