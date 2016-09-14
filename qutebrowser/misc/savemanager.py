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

"""Saving things to disk periodically."""

import os.path
import collections

from PyQt5.QtCore import pyqtSlot, QObject, QTimer

from qutebrowser.config import config
from qutebrowser.commands import cmdutils
from qutebrowser.utils import utils, log, message, objreg, usertypes


class Saveable:

    """A single thing which can be saved.

    Attributes:
        _name: The name of the thing to be saved.
        _dirty: Whether the saveable was changed since the last save.
        _save_handler: The function to call to save this Saveable.
        _save_on_exit: Whether to always save this saveable on exit.
        _config_opt: A (section, option) tuple of a config option which decides
                     whether to auto-save or not. None if no such option
                     exists.
        _filename: The filename of the underlying file.
    """

    def __init__(self, name, save_handler, changed=None, config_opt=None,
                 filename=None):
        self._name = name
        self._dirty = False
        self._save_handler = save_handler
        self._config_opt = config_opt
        if changed is not None:
            changed.connect(self.mark_dirty)
            self._save_on_exit = False
        else:
            self._save_on_exit = True
        self._filename = filename
        if filename is not None and not os.path.exists(filename):
            self._dirty = True
            self.save()

    def __repr__(self):
        return utils.get_repr(self, name=self._name, dirty=self._dirty,
                              save_handler=self._save_handler,
                              config_opt=self._config_opt,
                              save_on_exit=self._save_on_exit,
                              filename=self._filename)

    def mark_dirty(self):
        """Mark this saveable as dirty (having changes)."""
        log.save.debug("Marking {} as dirty.".format(self._name))
        self._dirty = True

    def save(self, is_exit=False, explicit=False, silent=False, force=False):
        """Save this saveable.

        Args:
            is_exit: Whether we're currently exiting qutebrowser.
            explicit: Whether the user explicitly requested this save.
            silent: Don't write informations to log.
            force: Force saving, no matter what.
        """
        if (self._config_opt is not None and
                (not config.get(*self._config_opt)) and
                (not explicit) and (not force)):
            if not silent:
                log.save.debug("Not saving {name} because autosaving has been "
                               "disabled by {cfg[0]} -> {cfg[1]}.".format(
                                   name=self._name, cfg=self._config_opt))
            return
        do_save = self._dirty or (self._save_on_exit and is_exit) or force
        if not silent:
            log.save.debug("Save of {} requested - dirty {}, save_on_exit {}, "
                           "is_exit {}, force {} -> {}".format(
                               self._name, self._dirty, self._save_on_exit,
                               is_exit, force, do_save))
        if do_save:
            self._save_handler()
            self._dirty = False


class SaveManager(QObject):

    """Responsible to save 'saveables' periodically and on exit.

    Attributes:
        saveables: A dict mapping names to Saveable instances.
        _save_timer: The Timer used to periodically auto-save things.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.saveables = collections.OrderedDict()
        self._save_timer = usertypes.Timer(self, name='save-timer')
        self._save_timer.timeout.connect(self.autosave)

    def __repr__(self):
        return utils.get_repr(self, saveables=self.saveables)

    def init_autosave(self):
        """Initialize auto-saving.

        We don't do this in __init__ because the config needs to be initialized
        first, but the config needs the save manager.
        """
        self.set_autosave_interval()
        objreg.get('config').changed.connect(self.set_autosave_interval)

    @config.change_filter('general', 'auto-save-interval')
    def set_autosave_interval(self):
        """Set the auto-save interval."""
        interval = config.get('general', 'auto-save-interval')
        if interval == 0:
            self._save_timer.stop()
        else:
            self._save_timer.setInterval(interval)
            self._save_timer.start()

    def add_saveable(self, name, save, changed=None, config_opt=None,
                     filename=None, dirty=False):
        """Add a new saveable.

        Args:
            name: The name to use.
            save: The function to call to save this saveable.
            changed: The signal emitted when this saveable changed.
            config_opt: A (section, option) tuple deciding whether to auto-save
                        or not.
            filename: The filename of the underlying file, so we can force
                      saving if it doesn't exist.
            dirty: Whether the saveable is already dirty.
        """
        if name in self.saveables:
            raise ValueError("Saveable {} already registered!".format(name))
        saveable = Saveable(name, save, changed, config_opt, filename)
        self.saveables[name] = saveable
        if dirty:
            saveable.mark_dirty()
            QTimer.singleShot(0, saveable.save)

    def save(self, name, is_exit=False, explicit=False, silent=False,
             force=False):
        """Save a saveable by name.

        Args:
            is_exit: Whether we're currently exiting qutebrowser.
            explicit: Whether this save operation was triggered explicitly.
            silent: Don't write informations to log. Used to reduce log spam
                    when autosaving.
            force: Force saving, no matter what.
        """
        self.saveables[name].save(is_exit=is_exit, explicit=explicit,
                                  silent=silent, force=force)

    @pyqtSlot()
    def autosave(self):
        """Slot used when the configs are auto-saved."""
        for (key, saveable) in self.saveables.items():
            try:
                saveable.save(silent=True)
            except OSError as e:
                message.error("Failed to auto-save {}: {}".format(key, e))

    @cmdutils.register(instance='save-manager', name='save',
                       star_args_optional=True)
    def save_command(self, *what):
        """Save configs and state.

        Args:
            *what: What to save (`config`/`key-config`/`cookies`/...).
                   If not given, everything is saved.
        """
        if what:
            explicit = True
        else:
            what = self.saveables
            explicit = False
        for key in what:
            if key not in self.saveables:
                message.error("{} is nothing which can be saved".format(key))
            else:
                try:
                    self.save(key, explicit=explicit, force=True)
                except OSError as e:
                    message.error("Could not save {}: {}".format(key, e))
        log.save.debug(":save saved {}".format(', '.join(what)))
