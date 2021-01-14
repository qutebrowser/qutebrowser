# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import sys
import json
import textwrap
import os
import signal
import time

import pytest
import pytest_bdd as bdd
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QFileSystemWatcher
bdd.scenarios('fileselect.feature')

from qutebrowser.utils import utils


@bdd.when(bdd.parsers.parse('I set up a fake single file fileselector '
                            'selecting "{choosefile}"'))
def set_up_single_fileselector(quteproc, server, tmpdir, choosefile):
    """Set up fileselect.single_file.command to select the file `chosenfile`."""
    fileselect_cmd = json.dumps(['cat', choosefile, '|', '{}'])
    quteproc.set_setting('fileselect.handler', 'external')
    quteproc.set_setting('fileselect.single_file.command', fileselect_cmd)


@bdd.when('I trigger to upload a file')
def trigger_upload_file(quteproc, server, tmpdir):
    """Trigger to upload a file."""
    raise NotImplementedError


@bdd.then(bdd.parsers.parse('"{chosenfile}" should be uploaded'))
def check_chosen_file(quteproc, server, tmpdir, chosenfile):
    """Check correct file is chosen."""
    raise NotImplementedError
