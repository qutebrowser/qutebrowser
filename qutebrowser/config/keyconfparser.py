# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Parser for the key configuration."""

import collections
import os.path

from qutebrowser.config import configdata, textwrapper
from qutebrowser.commands import cmdutils
from qutebrowser.utils import log


class KeyConfigError(Exception):

    """Raised on errors with the key config.

    Attributes:
        lineno: The config line in which the exception occured.
    """

    def __init__(self, msg=None):
        super().__init__(msg)
        self.lineno = None


class KeyConfigParser:

    """Parser for the keybind config."""

    def __init__(self, configdir, fname):
        """Constructor.

        Args:
            configdir: The directory to save the configs in.
            fname: The filename of the config.
        """
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        self._cur_section = None
        self._cur_command = None
        # Mapping of section name(s) to keybinding -> command dicts.
        self.keybindings = collections.OrderedDict()
        if not os.path.exists(self._configfile):
            self._load_default()
        else:
            self._read()
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
        with open(self._configfile, 'w', encoding='utf-8') as f:
            f.write(str(self))

    def _normalize_sectname(self, s):
        """Normalize a section string like 'foo, bar,baz' to 'bar,baz,foo'."""
        return ','.join(sorted(s.split(',')))

    def _load_default(self):
        """Load the built-in default keybindings."""
        for sectname, sect in configdata.KEY_DATA.items():
            sectname = self._normalize_sectname(sectname)
            for command, keychains in sect.items():
                for e in keychains:
                    self._add_binding(sectname, e, command)

    def _read(self):
        """Read the config file from disk and parse it."""
        with open(self._configfile, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line = line.rstrip()
                try:
                    if not line.strip() or line.startswith('#'):
                        continue
                    elif line.startswith('[') and line.endswith(']'):
                        sectname = line[1:-1]
                        self._cur_section = self._normalize_sectname(sectname)
                    elif line.startswith((' ', '\t')):
                        line = line.strip()
                        self._read_keybinding(line)
                    else:
                        line = line.strip()
                        self._read_command(line)
                except KeyConfigError as e:
                    e.lineno = i
                    raise

    def _read_command(self, line):
        """Read a command from a line."""
        if self._cur_section is None:
            raise KeyConfigError("Got command '{}' without getting a "
                                 "section!".format(line))
        else:
            command = line.split(maxsplit=1)[0]
            if command not in cmdutils.cmd_dict:
                raise KeyConfigError("Invalid command '{}'!".format(command))
            self._cur_command = line

    def _read_keybinding(self, line):
        """Read a keybinding from a line."""
        if self._cur_command is None:
            raise KeyConfigError("Got keybinding '{}' without getting a "
                                 "command!".format(line))
        else:
            assert self._cur_section is not None
            self._add_binding(self._cur_section, line, self._cur_command)

    def _add_binding(self, sectname, keychain, command):
        """Add a new binding from keychain to command in section sectname."""
        if sectname not in self.keybindings:
            self.keybindings[sectname] = collections.OrderedDict()
        if keychain in self.get_bindings_for(sectname):
            raise KeyConfigError("Duplicate keychain '{}'!".format(keychain))
        self.keybindings[sectname][keychain] = command

    def get_bindings_for(self, section):
        """Get a dict with all merged keybindings for a section."""
        bindings = {}
        for sectstring, d in self.keybindings.items():
            sects = [s.strip() for s in sectstring.split(',')]
            if any(s == section for s in sects):
                bindings.update(d)
        try:
            bindings.update(self.keybindings['all'])
        except KeyError:
            pass
        return bindings
