# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Parser for line-based files like histories."""

import os
import os.path
import contextlib
import typing

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject

from qutebrowser.utils import log, utils, qtutils
from qutebrowser.config import config


class BaseLineParser(QObject):

    """A LineParser without any real data.

    Attributes:
        _configdir: Directory to read the config from, or None.
        _configfile: The config file path.
        _fname: Filename of the config.
        _binary: Whether to open the file in binary mode.

    Signals:
        changed: Emitted when the history was changed.
    """

    changed = pyqtSignal()

    def __init__(self, configdir, fname, *, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            binary: Whether to open the file in binary mode.
            _opened: Whether the underlying file is open
        """
        super().__init__(parent)
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        self._fname = fname
        self._binary = binary
        self._opened = False

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              configdir=self._configdir, fname=self._fname,
                              binary=self._binary)

    def _prepare_save(self):
        """Prepare saving of the file.

        Return:
            True if the file should be saved, False otherwise.
        """
        os.makedirs(self._configdir, 0o755, exist_ok=True)
        return True

    def _after_save(self):
        """Log a message after saving is done."""
        log.destroy.debug("Saved to {}".format(self._configfile))

    @contextlib.contextmanager
    def _open(self, mode):
        """Open self._configfile for reading.

        Args:
            mode: The mode to use ('a'/'r'/'w')

        Raises:
            IOError: if the file is already open

        Yields:
            a file object for the config file
        """
        assert self._configfile is not None
        if self._opened:
            raise IOError("Refusing to double-open LineParser.")
        self._opened = True
        try:
            if self._binary:
                with open(self._configfile, mode + 'b') as f:
                    yield f
            else:
                with open(self._configfile, mode, encoding='utf-8') as f:
                    yield f
        finally:
            self._opened = False

    def _write(self, fp, data):
        """Write the data to a file.

        Args:
            fp: A file object to write the data to.
            data: The data to write.
        """
        if not data:
            return
        if self._binary:
            fp.write(b'\n'.join(data))
            fp.write(b'\n')
        else:
            fp.write('\n'.join(data))
            fp.write('\n')

    def save(self):
        """Save the history to disk."""
        raise NotImplementedError

    def clear(self):
        """Clear the contents of the file."""
        raise NotImplementedError


class LineParser(BaseLineParser):

    """Parser for configuration files which are simply line-based.

    Attributes:
        data: A list of lines.
    """

    def __init__(self, configdir, fname, *, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            binary: Whether to open the file in binary mode.
        """
        super().__init__(configdir, fname, binary=binary, parent=parent)
        if not os.path.isfile(self._configfile):
            self.data = []  # type: typing.Sequence[str]
        else:
            log.init.debug("Reading {}".format(self._configfile))
            self._read()

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def _read(self):
        """Read the data from self._configfile."""
        with self._open('r') as f:
            if self._binary:
                self.data = [line.rstrip(b'\n') for line in f]
            else:
                self.data = [line.rstrip('\n') for line in f]

    def save(self):
        """Save the config file."""
        if self._opened:
            raise IOError("Refusing to double-open LineParser.")
        do_save = self._prepare_save()
        if not do_save:
            return
        self._opened = True
        try:
            assert self._configfile is not None
            with qtutils.savefile_open(self._configfile, self._binary) as f:
                self._write(f, self.data)
        finally:
            self._opened = False
        self._after_save()

    def clear(self):
        self.data = []
        self.save()


class LimitLineParser(LineParser):

    """A LineParser with a limited count of lines.

    Attributes:
        _limit: The config option used to limit the maximum number of lines.
    """

    def __init__(self, configdir, fname, *, limit, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from, or None.
            fname: Filename of the config file.
            limit: Config option which contains a limit.
            binary: Whether to open the file in binary mode.
        """
        super().__init__(configdir, fname, binary=binary, parent=parent)
        self._limit = limit
        if limit is not None and configdir is not None:
            config.instance.changed.connect(self._cleanup_file)

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              configdir=self._configdir, fname=self._fname,
                              limit=self._limit, binary=self._binary)

    @pyqtSlot(str)
    def _cleanup_file(self, option):
        """Delete the file if the limit was changed to 0."""
        assert self._configfile is not None
        if option != self._limit:
            return
        value = config.instance.get(option)
        if value == 0:
            if os.path.exists(self._configfile):
                os.remove(self._configfile)

    def save(self):
        """Save the config file."""
        limit = config.instance.get(self._limit)
        if limit == 0:
            return
        do_save = self._prepare_save()
        if not do_save:
            return
        assert self._configfile is not None
        with qtutils.savefile_open(self._configfile, self._binary) as f:
            self._write(f, self.data[-limit:])
        self._after_save()
