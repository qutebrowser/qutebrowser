# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Parser for the key configuration."""

import collections
import os.path
import itertools

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.config import configdata, textwrapper
from qutebrowser.commands import cmdutils, cmdexc
from qutebrowser.utils import log, utils, qtutils, message, usertypes


class KeyConfigError(Exception):

    """Raised on errors with the key config.

    Attributes:
        lineno: The config line in which the exception occurred.
    """

    def __init__(self, msg=None):
        super().__init__(msg)
        self.lineno = None


class DuplicateKeychainError(KeyConfigError):

    """Error raised when there's a duplicate key binding."""

    def __init__(self, keychain):
        super().__init__("Duplicate key chain {}!".format(keychain))
        self.keychain = keychain


class KeyConfigParser(QObject):

    """Parser for the keybind config.

    Attributes:
        _configfile: The filename of the config or None.
        _cur_section: The section currently being processed by _read().
        _cur_command: The command currently being processed by _read().
        is_dirty: Whether the config is currently dirty.

    Class attributes:
        UNBOUND_COMMAND: The special command used for unbound keybindings.

    Signals:
        changed: Emitted when the internal data has changed.
                 arg: Name of the mode which was changed.
        config_dirty: Emitted when the config should be re-saved.
    """

    changed = pyqtSignal(str)
    config_dirty = pyqtSignal()
    UNBOUND_COMMAND = '<unbound>'

    def __init__(self, configdir, fname, relaxed=False, parent=None):
        """Constructor.

        Args:
            configdir: The directory to save the configs in.
            fname: The filename of the config.
            relaxed: If given, unknown commands are ignored.
        """
        super().__init__(parent)
        self.is_dirty = False
        self._cur_section = None
        self._cur_command = None
        # Mapping of section name(s) to key binding -> command dicts.
        self.keybindings = collections.OrderedDict()
        self._configfile = os.path.join(configdir, fname)

        if not os.path.exists(self._configfile):
            self._load_default()
        else:
            self._read(relaxed)
            self._load_default(only_new=True)
        log.init.debug("Loaded bindings: {}".format(self.keybindings))

    def __str__(self):
        """Get the config as string."""
        lines = configdata.KEY_FIRST_COMMENT.strip('\n').splitlines()
        lines.append('')
        for sectname, sect in self.keybindings.items():
            lines.append('[{}]'.format(sectname))
            lines += self._str_section_desc(sectname)
            lines.append('')
            data = collections.OrderedDict()
            for key, cmd in sect.items():
                if cmd in data:
                    data[cmd].append(key)
                else:
                    data[cmd] = [key]
            for cmd, keys in data.items():
                lines.append(cmd)
                for k in keys:
                    lines.append(' ' * 4 + k)
                lines.append('')
        return '\n'.join(lines) + '\n'

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              configfile=self._configfile)

    def _str_section_desc(self, sectname):
        """Get the section description string for sectname."""
        wrapper = textwrapper.TextWrapper()
        lines = []
        try:
            seclines = configdata.KEY_SECTION_DESC[sectname].splitlines()
        except KeyError:
            return []
        else:
            for secline in seclines:
                if 'http://' in secline or 'https://' in secline:
                    lines.append('# ' + secline)
                else:
                    lines += wrapper.wrap(secline)
            return lines

    def save(self):
        """Save the key config file."""
        log.destroy.debug("Saving key config to {}".format(self._configfile))
        with qtutils.savefile_open(self._configfile, encoding='utf-8') as f:
            data = str(self)
            f.write(data)

    @cmdutils.register(instance='key-config', maxsplit=1, no_cmd_split=True,
                       no_replace_variables=True)
    @cmdutils.argument('command', completion=usertypes.Completion.bind)
    def bind(self, key, command=None, *, mode='normal', force=False):
        """Bind a key to a command.

        Args:
            key: The keychain or special key (inside `<...>`) to bind.
            command: The command to execute, with optional args, or None to
                     print the current binding.
            mode: A comma-separated list of modes to bind the key in
                  (default: `normal`).
            force: Rebind the key if it is already bound.
        """
        if utils.is_special_key(key):
            # <Ctrl-t>, <ctrl-T>, and <ctrl-t> should be considered equivalent
            key = key.lower()

        if command is None:
            cmd = self.get_bindings_for(mode).get(key, None)
            if cmd is None:
                message.info("{} is unbound in {} mode".format(key, mode))
            else:
                message.info("{} is bound to '{}' in {} mode".format(key, cmd,
                                                                     mode))
            return

        modenames = self._normalize_sectname(mode).split(',')
        for m in modenames:
            if m not in configdata.KEY_DATA:
                raise cmdexc.CommandError("Invalid mode {}!".format(m))
        try:
            modes = [usertypes.KeyMode[m] for m in modenames]
            self._validate_command(command, modes)
        except KeyConfigError as e:
            raise cmdexc.CommandError(str(e))
        try:
            self._add_binding(mode, key, command, force=force)
        except DuplicateKeychainError as e:
            raise cmdexc.CommandError("Duplicate keychain {} - use --force to "
                                      "override!".format(str(e.keychain)))
        except KeyConfigError as e:
            raise cmdexc.CommandError(e)
        for m in modenames:
            self.changed.emit(m)
            self._mark_config_dirty()

    @cmdutils.register(instance='key-config')
    def unbind(self, key, mode='normal'):
        """Unbind a keychain.

        Args:
            key: The keychain or special key (inside <...>) to unbind.
            mode: A comma-separated list of modes to unbind the key in
                  (default: `normal`).
        """
        if utils.is_special_key(key):
            # <Ctrl-t>, <ctrl-T>, and <ctrl-t> should be considered equivalent
            key = key.lower()

        mode = self._normalize_sectname(mode)
        for m in mode.split(','):
            if m not in configdata.KEY_DATA:
                raise cmdexc.CommandError("Invalid mode {}!".format(m))
        try:
            sect = self.keybindings[mode]
        except KeyError:
            raise cmdexc.CommandError("Can't find mode section '{}'!".format(
                mode))
        try:
            del sect[key]
        except KeyError:
            raise cmdexc.CommandError("Can't find binding '{}' in section "
                                      "'{}'!".format(key, mode))
        else:
            if key in itertools.chain.from_iterable(
                    configdata.KEY_DATA[mode].values()):
                try:
                    self._add_binding(mode, key, self.UNBOUND_COMMAND)
                except DuplicateKeychainError:
                    pass
            for m in mode.split(','):
                self.changed.emit(m)
            self._mark_config_dirty()

    def _normalize_sectname(self, s):
        """Normalize a section string like 'foo, bar,baz' to 'bar,baz,foo'."""
        if s.startswith('!'):
            inverted = True
            s = s[1:]
        else:
            inverted = False
        sections = ','.join(sorted(s.split(',')))
        if inverted:
            sections = '!' + sections
        return sections

    def _load_default(self, *, only_new=False):
        """Load the built-in default key bindings.

        Args:
            only_new: If set, only keybindings which are completely unused
                      (same command/key not bound) are added.
        """
        # {'sectname': {'keychain1': 'command', 'keychain2': 'command'}, ...}
        bindings_to_add = collections.OrderedDict()

        for sectname, sect in configdata.KEY_DATA.items():
            sectname = self._normalize_sectname(sectname)
            bindings_to_add[sectname] = collections.OrderedDict()
            for command, keychains in sect.items():
                for e in keychains:
                    if not only_new or self._is_new(sectname, command, e):
                        assert e not in bindings_to_add[sectname]
                        bindings_to_add[sectname][e] = command

        for sectname, sect in bindings_to_add.items():
            if not sect:
                if not only_new:
                    self.keybindings[sectname] = collections.OrderedDict()
            else:
                for keychain, command in sect.items():
                    self._add_binding(sectname, keychain, command)
            self.changed.emit(sectname)

        if bindings_to_add:
            self._mark_config_dirty()

    def _is_new(self, sectname, command, keychain):
        """Check if a given binding is new.

        A binding is considered new if both the command is not bound to any key
        yet, and the key isn't used anywhere else in the same section.
        """
        if utils.is_special_key(keychain):
            keychain = keychain.lower()

        try:
            bindings = self.keybindings[sectname]
        except KeyError:
            return True
        if keychain in bindings:
            return False
        else:
            return command not in bindings.values()

    def _read(self, relaxed=False):
        """Read the config file from disk and parse it.

        Args:
            relaxed: Ignore unknown commands.
        """
        try:
            with open(self._configfile, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    line = line.rstrip()
                    try:
                        if not line.strip() or line.startswith('#'):
                            continue
                        elif line.startswith('[') and line.endswith(']'):
                            sectname = line[1:-1]
                            self._cur_section = self._normalize_sectname(
                                sectname)
                        elif line.startswith((' ', '\t')):
                            line = line.strip()
                            self._read_keybinding(line)
                        else:
                            line = line.strip()
                            self._read_command(line)
                    except KeyConfigError as e:
                        if relaxed:
                            continue
                        else:
                            e.lineno = i
                            raise
        except OSError:
            log.keyboard.exception("Failed to read key bindings!")
        for sectname in self.keybindings:
            self.changed.emit(sectname)

    def _mark_config_dirty(self):
        """Mark the config as dirty."""
        self.is_dirty = True
        self.config_dirty.emit()

    def _validate_command(self, line, modes=None):
        """Check if a given command is valid.

        Args:
            line: The commandline to validate.
            modes: A list of modes to validate the commands for, or None.
        """
        from qutebrowser.config import config
        if line == self.UNBOUND_COMMAND:
            return
        commands = line.split(';;')
        try:
            first_cmd = commands[0].split(maxsplit=1)[0].strip()
            cmd = cmdutils.cmd_dict[first_cmd]
            if cmd.no_cmd_split:
                commands = [line]
        except (KeyError, IndexError):
            pass

        for cmd in commands:
            if not cmd.strip():
                raise KeyConfigError("Got empty command (line: {!r})!".format(
                    line))
        commands = [c.split(maxsplit=1)[0].strip() for c in commands]
        for cmd in commands:
            aliases = config.section('aliases')
            if cmd in cmdutils.cmd_dict:
                cmdname = cmd
            elif cmd in aliases:
                cmdname = aliases[cmd].split(maxsplit=1)[0].strip()
            else:
                raise KeyConfigError("Invalid command '{}'!".format(cmd))
            cmd_obj = cmdutils.cmd_dict[cmdname]
            for m in modes or []:
                cmd_obj.validate_mode(m)

    def _read_command(self, line):
        """Read a command from a line."""
        if self._cur_section is None:
            raise KeyConfigError("Got command '{}' without getting a "
                                 "section!".format(line))
        else:
            for rgx, repl in configdata.CHANGED_KEY_COMMANDS:
                if rgx.match(line):
                    line = rgx.sub(repl, line)
                    self._mark_config_dirty()
                    break
            self._validate_command(line)
            self._cur_command = line

    def _read_keybinding(self, line):
        """Read a key binding from a line."""
        if self._cur_command is None:
            raise KeyConfigError("Got key binding '{}' without getting a "
                                 "command!".format(line))
        else:
            assert self._cur_section is not None
            self._add_binding(self._cur_section, line, self._cur_command)

    def _add_binding(self, sectname, keychain, command, *, force=False):
        """Add a new binding from keychain to command in section sectname."""
        if utils.is_special_key(keychain):
            # <Ctrl-t>, <ctrl-T>, and <ctrl-t> should be considered equivalent
            keychain = keychain.lower()
        log.keyboard.vdebug("Adding binding {} -> {} in mode {}.".format(
            keychain, command, sectname))
        if sectname not in self.keybindings:
            self.keybindings[sectname] = collections.OrderedDict()
        if keychain in self.get_bindings_for(sectname):
            if force or command == self.UNBOUND_COMMAND:
                self.unbind(keychain, mode=sectname)
            else:
                raise DuplicateKeychainError(keychain)
        section = self.keybindings[sectname]
        if (command != self.UNBOUND_COMMAND and
                section.get(keychain, None) == self.UNBOUND_COMMAND):
            # re-binding an unbound keybinding
            del section[keychain]
        self.keybindings[sectname][keychain] = command

    def get_bindings_for(self, section):
        """Get a dict with all merged key bindings for a section."""
        bindings = {}
        for sectstring, d in self.keybindings.items():
            if sectstring.startswith('!'):
                inverted = True
                sectstring = sectstring[1:]
            else:
                inverted = False
            sects = [s.strip() for s in sectstring.split(',')]
            matches = any(s == section for s in sects)
            if (not inverted and matches) or (inverted and not matches):
                bindings.update(d)
        try:
            bindings.update(self.keybindings['all'])
        except KeyError:
            pass
        bindings = {k: v for k, v in bindings.items()
                    if v != self.UNBOUND_COMMAND}
        return bindings

    def get_reverse_bindings_for(self, section):
        """Get a dict of commands to a list of bindings for the section."""
        cmd_to_keys = {}
        for key, cmd in self.get_bindings_for(section).items():
            cmd_to_keys.setdefault(cmd, [])
            # put special bindings last
            if utils.is_special_key(key):
                cmd_to_keys[cmd].append(key)
            else:
                cmd_to_keys[cmd].insert(0, key)
        return cmd_to_keys
