# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generic settings status displayed in the statusbar."""

import functools

from typing import TYPE_CHECKING, Dict, Optional

from qutebrowser.qt.core import pyqtSlot, QUrl
from qutebrowser.qt.widgets import QWidget

from qutebrowser.config import config, configtypes
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import objreg, usertypes, message
from qutebrowser.browser.browsertab import WebTabError, FeatureState

if TYPE_CHECKING:
    from qutebrowser.browser.browsertab import AbstractTab


class BooleanSettings(textbase.TextBase):

    """Boolean settings state displayed in the statusbar."""

    config_option = 'statusbar.settings'

    def __init__(self, parent: QWidget, win_id: int):
        super().__init__(parent)
        self._win_id = win_id
        # A dict of setting_name -> indicator mappings.
        self._config: Dict[str, str] = {}
        self.enabled = False
        self._text_for = functools.lru_cache(maxsize=256)(
            self._text_for_uncached
        )
        self._parse_config()

    def _test_feature(self, setting_name: str) -> Optional[bool]:
        tab = self._current_tab()
        if not tab:
            return None
        state = tab.permissions.test_feature(setting_name)
        return state == FeatureState.granted

    def _to_bool(self, setting_name: str, url: QUrl) -> bool:
        """Return a bool for Bool and BoolAsk settings."""
        opt = config.instance.get_opt(setting_name)
        obj = config.instance.get_obj(
            setting_name,
            url=url if opt.supports_pattern else None,
        )
        if isinstance(opt.typ, configtypes.BoolAsk):
            feature_state = None
            try:
                feature_state = self._test_feature(setting_name)
            except WebTabError as err:
                message.error(str(err))
            if feature_state is None:
                return obj is True
            return feature_state
        return obj

    def _parse_config(self) -> None:
        """Parse and apply settings from the config option."""
        self._config = config.instance.get(self.config_option)

        tab = self._current_tab()
        if tab:
            self.on_url_changed(tab.url())

    def _text_for_uncached(self, url: QUrl) -> str:
        parts = [
            indicator for setting, indicator in self._config.items()
            if self._to_bool(setting, url)
        ]
        return "[{}]".format(''.join(parts))

    @pyqtSlot(QUrl)
    def on_url_changed(self, url: QUrl) -> None:
        """Update the widget to reflect settings for url."""
        self.setVisible(self.enabled)
        if not self.enabled:
            return
        self.setText(self._text_for(url if url.isValid() else None))

    def on_tab_changed(self, tab: 'AbstractTab') -> None:
        """Update tab settings text when tab changed."""
        if not tab:
            # Probably some timing issue with tabs/windows closing down.
            return
        self.on_url_changed(tab.url())

    @pyqtSlot(usertypes.LoadStatus)
    def on_load_status_changed(self, _status: usertypes.LoadStatus) -> None:
        """Update widget when load status changed."""
        self.on_tab_changed(self._current_tab())

    def _current_tab(self) -> 'AbstractTab':
        """Get the currently displayed tab."""
        window = objreg.get('tabbed-browser', scope='window',
                            window=self._win_id)
        return window.widget.currentWidget()

    def on_config_changed(self, option: str) -> None:
        """Update the widget when the config changes."""
        self._text_for.cache_clear()
        if option == self.config_option:
            self._parse_config()
        elif option in self._config:
            self.on_tab_changed(self._current_tab())

    @pyqtSlot(str, FeatureState)
    def on_feature_permission_changed(
        self, option: str, _state: FeatureState,
    ) -> None:
        """Update the widget when a pages feature permissions change."""
        if option in self._config:
            self._text_for.cache_clear()
            self.on_tab_changed(self._current_tab())
