# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Management of per domain settings."""

import os

from PyQt5.QtCore import pyqtSignal, QUrl, QObject
from PyQt5.QtWebKit import QWebSettings

import yaml
try:
    from yaml import CSafeLoader as YamlLoader, CSafeDumper as YamlDumper
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as YamlLoader, SafeDumper as YamlDumper

from qutebrowser.utils import (standarddir, objreg, qtutils, log, message)
from qutebrowser.commands import cmdutils

def init(parent=None):
    """Initialize domain settings.

    Args:
        parent: The parent to use for the DomainManager.
    """
    data_dir = standarddir.data()
    if data_dir is None:
        base_path = None
    else:
        base_path = os.path.join(standarddir.data(), 'domains.yml')

    domain_manager = DomainManager(base_path, parent)
    domain_manager.load()
    objreg.register('domain-manager', domain_manager)

class DomainError(Exception):

    """Exception raised when domain settings failed to load/save."""

class DomainManager(QObject):
    # TODO: temporary settings that are not saved to disc.

    domain_settings_changed = pyqtSignal()

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.data = {}

    def load(self):
        """Load domain settings from file.
        """
        log.domains.debug("Loading domain settings from {}...".format(self.path))
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as f:
                pass
        try:
            with open(self.path, encoding='utf-8') as f:
                self.data = yaml.load(f, Loader=YamlLoader)
                if not self.data:
                    self.data = {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            raise DomainError(e)

        objreg.get('save-manager').add_saveable('domain',
                                                self.save,
                                                self.domain_settings_changed)

    def save(self):
        """Save domain settings to file.
        """
        log.domains.debug("Saving domain settings to {}...".format(self.path))
        try:
            with qtutils.savefile_open(self.path) as f:
                yaml.dump(self.data, f, Dumper=YamlDumper, default_flow_style=False,
                          encoding='utf-8', allow_unicode=True)
        except (OSError, UnicodeEncodeError, yaml.YAMLError) as e:
            raise DomainError(e)

    @cmdutils.register(name=['script-toggle'], win_id='win_id',
                       instance='domain-manager')
    def script_toggle(self, page=False, remove=False, win_id=None):
        """Toggle javascript policy for host or url of current tab.

        Args:
            page: toggle for domain (False) or just this url (True)
            remove: remove domain/url from white/blacklist
        """
        full_url = objreg.get('tabbed-browser', scope='window',
                              window='current').current_url()
        if not page:
            part = full_url.host()
        else:
            part = full_url.host()+full_url.path()
        
        domain_settings = self.data.get(part, {})
        if remove or 'enable-javascript' not in domain_settings:
            old_policy = QWebSettings.globalSettings().testAttribute(
                    QWebSettings.JavascriptEnabled)
        else:
            old_policy = domain_settings['enable-javascript']
        if remove:
            if 'enable-javascript' in domain_settings:
                del domain_settings['enable-javascript']
        else:
            domain_settings['enable-javascript'] = not old_policy

        if not domain_settings:
            if part in self.data:
                del self.data[part]
                log.domains.debug("No more settings for "+part)
        else:
            self.data[part] = domain_settings

        msg="Scripts {} for {}: {}".format(
            "blocked" if old_policy else "allowed",
            "url" if page else "domain",
            part)
        if win_id is None:
            log.domains.debug(msg)
        else:
            message.info(win_id, msg, immediately=True)

        self.domain_settings_changed.emit()

    def get_setting(self, url, setting=None, default=None):
        """Get per domain settings.

        Args:
            url: the domain or url to get the settings for
            setting: get just this setting for the page (falsy for a
                dict of all of them)
            default: value to return on non-existence
        """
        domain_setting = self.data.get(url, None)
        if not domain_setting:
            return default
        if not setting:
            return domain_setting
        return domain_setting.get(setting, default)
