# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Generic settings status displayed in the statusbar."""

from qutebrowser.config import config, configtypes
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import objreg, message


class BooleanSettings(textbase.TextBase):

    """Boolean settings state displayed in the statusbar."""

    # A list of indicator, setting_name pairs.
    _config = []
    config_option = 'settings.widget.content'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parse_config()

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
            if obj == 'ask':
                return False
            return obj
        elif isinstance(opt.typ, configtypes.Bool):
            return obj
        raise ValueError(
            "Setting '{}' is not a boolean setting."
            .format(setting_name)
        )

    def parse_config(self):
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

    def on_load_status_changed(self, _status):
        """Update widget when load status changed."""
        self.on_tab_changed(self._current_tab())

    def _current_tab(self):
        """Get the currently displayed tab."""
        # pylint: disable=protected-access
        window = objreg.get('tabbed-browser', scope='window',
                            window=self.parent()._win_id)
        return window.widget.currentWidget()

    def on_config_changed(self, option):
        """Update the widget when the config changes."""
        if option == self.config_option:
            self.parse_config()
        elif option in [t[1] for t in self._config]:
            self.on_tab_changed(self._current_tab())
