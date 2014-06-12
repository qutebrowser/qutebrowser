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

"""Utilities to show various version informations."""

import sys
import glob
import os.path
import platform
import subprocess

from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from PyQt5.QtWebKit import qWebKitVersion

import qutebrowser
from qutebrowser.utils.misc import read_file


GPL_BOILERPLATE = """
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/> or use
:open qute:gpl.
"""

GPL_BOILERPLATE_HTML = """
<p>
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
</p>
<p>
This program is distributed in the hope that it will be useful,
but <b>without any warranty</b>; without even the implied warranty of
<b>merchantability</b> or <b>fitness for a particular purpose</b>.  See the
GNU General Public License for more details.
</p>
<p>
You should have received a copy of the GNU General Public License
along with this program.  If not, see <a href="http://www.gnu.org/licenses/">
http://www.gnu.org/licenses/</a> or open <a href="qute:gpl">qute:gpl</a>.
"""


def _git_str():
    """Try to find out git version.

    Return:
        string containing the git commit ID.
        None if there was an error or we're not in a git repo.
    """
    # First try via subprocess if possible
    commit = None
    if not hasattr(sys, "frozen"):
        try:
            gitpath = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   os.path.pardir, os.path.pardir)
        except NameError:
            pass
        else:
            commit = _git_str_subprocess(gitpath)
    if commit is not None:
        return commit
    # If that fails, check the git-commit-id file.
    try:
        return read_file('git-commit-id')
    except (FileNotFoundError, ImportError):
        return None


def _git_str_subprocess(gitpath):
    """Try to get the git commit ID by calling git.

    Args:
        gitpath: The path where the .git folder is.

    Return:
        The path on success, None on failure.
    """
    if not os.path.isdir(os.path.join(gitpath, ".git")):
        return None
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=gitpath).decode('UTF-8').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _release_info():
    """Try to gather distribution release informations.

    Return:
        list of (filename, content) tuples.
    """
    data = []
    for fn in glob.glob("/etc/*-release"):
        try:
            with open(fn, 'r') as f:
                data.append((fn, ''.join(f.readlines())))
        except IOError:
            pass
    return data


def _module_versions():
    """Get versions of optional modules.

    Return:
        A list of lines with version info.
    """
    # pylint: disable=import-error, unused-variable
    lines = []
    try:
        import sipconfig
    except ImportError:
        pass
    else:
        try:
            lines.append('SIP: {}'.format(
                sipconfig.Configuration().sip_version_str))
        except (AttributeError, TypeError):
            lines.append('SIP: ?')

    try:
        import ipdb
        import IPython
    except ImportError:
        pass
    else:
        ver = getattr(IPython, '__version__', 'yes')
        lines.append('ipdb/IPython: {}'.format(ver))

    try:
        import colorlog
    except ImportError:
        pass
    else:
        lines.append('colorlog: yes')

    try:
        import colorama
    except ImportError:
        pass
    else:
        ver = getattr(colorama, 'VERSION', 'yes')
        lines.append('colorama: {}'.format(ver))

    return lines


def _os_info():
    """Get operating system info.

    Return:
        A list of lines with version info.
    """
    lines = []
    releaseinfo = None
    if sys.platform == 'linux':
        osver = ', '.join([e for e in platform.dist() if e])
        releaseinfo = _release_info()
    elif sys.platform == 'win32':
        osver = ', '.join(platform.win32_ver())
    elif sys.platform == 'darwin':
        osver = ', '.join(platform.mac_ver())
    else:
        osver = '?'
    lines.append('OS Version: {}'.format(osver))
    if releaseinfo is not None:
        for (fn, data) in releaseinfo:
            lines += ['', '--- {} ---'.format(fn), data]
    return lines


def version():
    """Return a string with various version informations."""
    lines = ["qutebrowser v{}".format(qutebrowser.__version__)]
    gitver = _git_str()
    if gitver is not None:
        lines.append("Git commit: {}".format(gitver))
    lines += [
        '',
        '{}: {}'.format(platform.python_implementation(),
                        platform.python_version()),
        'Qt: {}, runtime: {}'.format(QT_VERSION_STR, qVersion()),
        'PyQt: {}'.format(PYQT_VERSION_STR),
    ]
    lines += _module_versions()
    lines += [
        'Webkit: {}'.format(qWebKitVersion()),
        'Harfbuzz: {}'.format(os.environ.get('QT_HARFBUZZ', 'system')),
        '',
        'Platform: {}, {}'.format(platform.platform(),
                                  platform.architecture()[0]),
    ]
    lines += _os_info()
    return '\n'.join(lines)
