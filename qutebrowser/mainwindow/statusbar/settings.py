# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generic settings status displayed in the statusbar."""

from qutebrowser.qt.core import pyqtSlot, QUrl

from qutebrowser.config import config, configtypes
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import objreg, message, usertypes
from qutebrowser.browser.browsertab import WebTabError


class BooleanSettings(textbase.TextBase):

    """Boolean settings state displayed in the statusbar."""

    config_option = 'statusbar.settings'

    def __init__(self, parent, win_id, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._win_id = win_id
        # A list of indicator, setting_name pairs.
        self._config = []
        self._parse_config()

    def _test_feature(self, setting_name, default=False):
        tab = self._current_tab()
        if not tab:
            return default
        try:
            return tab.test_feature(setting_name)
        except WebTabError:
            return default

    def _to_bool(self, setting_name, url):
        """Return a bool for Bool and BoolAsk settings."""
        try:
            opt = config.instance.get_opt(setting_name)
        except config.configexc.Error as err:
            raise ValueError(str(err))
        if not opt.supports_pattern:
            url = None
        obj = config.instance.get_obj(setting_name, url=url)
        if isinstance(opt.typ, configtypes.BoolAsk):
            default = False if obj == 'ask' else obj
            return self._test_feature(setting_name, default=default)
        elif isinstance(opt.typ, configtypes.Bool):
            return obj
        raise ValueError(
            "Setting '{}' is not a boolean setting."
            .format(setting_name)
        )

    def _parse_config(self):
        """Parse settings from the config option.

        A ValueError will be raised for any errors in parsing or
        applying the settings.
        """
        raw = config.instance.get(self.config_option)
        config_ = [x.split('|') for x in raw if x.strip()]
        # Use `_to_bool()` to do some early validation
        for part in config_:
            try:
                _indicater, value = part
                self._to_bool(value, None)
            except ValueError as err:
                message.error(
                    "Error parsing '{}' setting value {}: {}"
                    .format(self.config_option, part, err)
                )
                return
        self._config = config_
        tab = self._current_tab()
        if tab:
            self.on_url_changed(tab.url())

    @pyqtSlot(QUrl)
    def on_url_changed(self, url):
        """Update the widget to reflect settings for url."""
        if not url.isValid():
            url = None
        parts = [
            t[0] for t in self._config
            if self._to_bool(t[1], url)
        ]
        self.setText("[{}]".format(''.join(parts)))

    def on_tab_changed(self, tab):
        """Update tab settings text when tab changed."""
        self.on_url_changed(tab.url())

    @pyqtSlot(usertypes.LoadStatus)
    def on_load_status_changed(self, _status):
        """Update widget when load status changed."""
        self.on_tab_changed(self._current_tab())

    def _current_tab(self):
        """Get the currently displayed tab."""
        window = objreg.get('tabbed-browser', scope='window',
                            window=self._win_id)
        return window.widget.currentWidget()

    def on_config_changed(self, option):
        """Update the widget when the config changes."""
        if option == self.config_option:
            self._parse_config()
        elif option in [t[1] for t in self._config]:
            self.on_tab_changed(self._current_tab())

    @pyqtSlot(str, bool)
    def on_feature_permission_changed(self, option, _enabled):
        """Update the widget when a pages feature permissions change."""
        if option in [t[1] for t in self._config]:
            self.on_tab_changed(self._current_tab())