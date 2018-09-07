#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Enforce perfect coverage on some files."""

import os
import os.path
import sys
import enum
import subprocess
from xml.etree import ElementTree

import attr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils as scriptutils
from qutebrowser.utils import utils


@attr.s
class Message:

    """A message shown by coverage.py."""

    typ = attr.ib()
    filename = attr.ib()
    text = attr.ib()


MsgType = enum.Enum('MsgType', 'insufficent_coverage, perfect_file')


# A list of (test_file, tested_file) tuples. test_file can be None.
PERFECT_FILES = [
    (None,
     'commands/cmdexc.py'),
    ('tests/unit/commands/test_cmdutils.py',
     'commands/cmdutils.py'),
    ('tests/unit/commands/test_argparser.py',
     'commands/argparser.py'),

    ('tests/unit/browser/webkit/test_cache.py',
     'browser/webkit/cache.py'),
    ('tests/unit/browser/webkit/test_cookies.py',
     'browser/webkit/cookies.py'),
    ('tests/unit/browser/test_history.py',
     'browser/history.py'),
    ('tests/unit/browser/test_pdfjs.py',
     'browser/pdfjs.py'),
    ('tests/unit/browser/webkit/http/test_http.py',
     'browser/webkit/http.py'),
    ('tests/unit/browser/webkit/http/test_content_disposition.py',
     'browser/webkit/rfc6266.py'),
    # ('tests/unit/browser/webkit/test_webkitelem.py',
    #  'browser/webkit/webkitelem.py'),
    # ('tests/unit/browser/webkit/test_webkitelem.py',
    #  'browser/webelem.py'),
    ('tests/unit/browser/webkit/network/test_filescheme.py',
     'browser/webkit/network/filescheme.py'),
    ('tests/unit/browser/webkit/network/test_networkreply.py',
     'browser/webkit/network/networkreply.py'),

    ('tests/unit/browser/test_signalfilter.py',
     'browser/signalfilter.py'),
    (None,
     'browser/webengine/certificateerror.py'),
    # ('tests/unit/browser/test_tab.py',
    #  'browser/tab.py'),

    ('tests/unit/keyinput/test_basekeyparser.py',
     'keyinput/basekeyparser.py'),
    ('tests/unit/keyinput/test_keyutils.py',
     'keyinput/keyutils.py'),

    ('tests/unit/misc/test_autoupdate.py',
     'misc/autoupdate.py'),
    ('tests/unit/misc/test_readline.py',
     'misc/readline.py'),
    ('tests/unit/misc/test_split.py',
     'misc/split.py'),
    ('tests/unit/misc/test_msgbox.py',
     'misc/msgbox.py'),
    ('tests/unit/misc/test_checkpyver.py',
     'misc/checkpyver.py'),
    ('tests/unit/misc/test_guiprocess.py',
     'misc/guiprocess.py'),
    ('tests/unit/misc/test_editor.py',
     'misc/editor.py'),
    ('tests/unit/misc/test_cmdhistory.py',
     'misc/cmdhistory.py'),
    ('tests/unit/misc/test_ipc.py',
     'misc/ipc.py'),
    ('tests/unit/misc/test_keyhints.py',
     'misc/keyhintwidget.py'),
    ('tests/unit/misc/test_pastebin.py',
     'misc/pastebin.py'),
    (None,
     'misc/objects.py'),

    (None,
     'mainwindow/statusbar/keystring.py'),
    ('tests/unit/mainwindow/statusbar/test_percentage.py',
     'mainwindow/statusbar/percentage.py'),
    ('tests/unit/mainwindow/statusbar/test_progress.py',
     'mainwindow/statusbar/progress.py'),
    ('tests/unit/mainwindow/statusbar/test_tabindex.py',
     'mainwindow/statusbar/tabindex.py'),
    ('tests/unit/mainwindow/statusbar/test_textbase.py',
     'mainwindow/statusbar/textbase.py'),
    ('tests/unit/mainwindow/statusbar/test_url.py',
     'mainwindow/statusbar/url.py'),
    ('tests/unit/mainwindow/statusbar/test_backforward.py',
     'mainwindow/statusbar/backforward.py'),
    ('tests/unit/mainwindow/test_messageview.py',
     'mainwindow/messageview.py'),

    ('tests/unit/config/test_config.py',
     'config/config.py'),
    ('tests/unit/config/test_configdata.py',
     'config/configdata.py'),
    ('tests/unit/config/test_configexc.py',
     'config/configexc.py'),
    ('tests/unit/config/test_configfiles.py',
     'config/configfiles.py'),
    ('tests/unit/config/test_configtypes.py',
     'config/configtypes.py'),
    ('tests/unit/config/test_configinit.py',
     'config/configinit.py'),
    ('tests/unit/config/test_configcommands.py',
     'config/configcommands.py'),
    ('tests/unit/config/test_configutils.py',
     'config/configutils.py'),
    ('tests/unit/config/test_configcache.py',
     'config/configcache.py'),

    ('tests/unit/utils/test_qtutils.py',
     'utils/qtutils.py'),
    ('tests/unit/utils/test_standarddir.py',
     'utils/standarddir.py'),
    ('tests/unit/utils/test_urlutils.py',
     'utils/urlutils.py'),
    ('tests/unit/utils/usertypes',
     'utils/usertypes.py'),
    ('tests/unit/utils/test_utils.py',
     'utils/utils.py'),
    ('tests/unit/utils/test_version.py',
     'utils/version.py'),
    ('tests/unit/utils/test_debug.py',
     'utils/debug.py'),
    ('tests/unit/utils/test_jinja.py',
     'utils/jinja.py'),
    ('tests/unit/utils/test_error.py',
     'utils/error.py'),
    ('tests/unit/utils/test_javascript.py',
     'utils/javascript.py'),
    ('tests/unit/utils/test_urlmatch.py',
     'utils/urlmatch.py'),

    (None,
     'completion/models/util.py'),
    ('tests/unit/completion/test_models.py',
     'completion/models/urlmodel.py'),
    ('tests/unit/completion/test_models.py',
     'completion/models/configmodel.py'),
    ('tests/unit/completion/test_histcategory.py',
     'completion/models/histcategory.py'),
    ('tests/unit/completion/test_listcategory.py',
     'completion/models/listcategory.py'),

    ('tests/unit/browser/webengine/test_spell.py',
     'browser/webengine/spell.py'),

]


# 100% coverage because of end2end tests, but no perfect unit tests yet.
WHITELISTED_FILES = [
    'browser/webkit/webkitinspector.py',
    'keyinput/macros.py',
    'browser/webkit/webkitelem.py',
]


class Skipped(Exception):

    """Exception raised when skipping coverage checks."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__("Skipping coverage checks " + reason)


def _get_filename(filename):
    """Transform the absolute test filenames to relative ones."""
    if os.path.isabs(filename):
        basedir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..'))
        common_path = os.path.commonprefix([basedir, filename])
        if common_path:
            filename = filename[len(common_path):].lstrip('/')
    if filename.startswith('qutebrowser/'):
        filename = filename.split('/', maxsplit=1)[1]

    return filename


def check(fileobj, perfect_files):
    """Main entry point which parses/checks coverage.xml if applicable."""
    if not utils.is_linux:
        raise Skipped("on non-Linux system.")
    elif '-k' in sys.argv[1:]:
        raise Skipped("because -k is given.")
    elif '-m' in sys.argv[1:]:
        raise Skipped("because -m is given.")
    elif '--lf' in sys.argv[1:]:
        raise Skipped("because --lf is given.")

    perfect_src_files = [e[1] for e in perfect_files]

    filename_args = [arg for arg in sys.argv[1:]
                     if arg.startswith('tests' + os.sep)]
    filtered_files = [tpl[1] for tpl in perfect_files if tpl[0] in
                      filename_args]

    if filename_args and not filtered_files:
        raise Skipped("because there is nothing to check.")

    tree = ElementTree.parse(fileobj)
    classes = tree.getroot().findall('./packages/package/classes/class')

    messages = []

    for klass in classes:
        filename = _get_filename(klass.attrib['filename'])

        line_cov = float(klass.attrib['line-rate']) * 100
        branch_cov = float(klass.attrib['branch-rate']) * 100

        if filtered_files and filename not in filtered_files:
            continue

        assert 0 <= line_cov <= 100, line_cov
        assert 0 <= branch_cov <= 100, branch_cov
        assert '\\' not in filename, filename

        is_bad = line_cov < 100 or branch_cov < 100

        if filename in perfect_src_files and is_bad:
            text = "{} has {:.2f}% line and {:.2f}% branch coverage!".format(
                filename, line_cov, branch_cov)
            messages.append(Message(MsgType.insufficent_coverage, filename,
                                    text))
        elif (filename not in perfect_src_files and not is_bad and
              filename not in WHITELISTED_FILES):
            text = ("{} has 100% coverage but is not in "
                    "perfect_files!".format(filename))
            messages.append(Message(MsgType.perfect_file, filename, text))

    return messages


def main_check():
    """Check coverage after a test run."""
    try:
        with open('coverage.xml', encoding='utf-8') as f:
            messages = check(f, PERFECT_FILES)
    except Skipped as e:
        print(e)
        messages = []

    if messages:
        print()
        print()
        scriptutils.print_title("Coverage check failed")
        for msg in messages:
            print(msg.text)
        print()
        filters = ','.join('qutebrowser/' + msg.filename for msg in messages)
        subprocess.run([sys.executable, '-m', 'coverage', 'report',
                        '--show-missing', '--include', filters], check=True)
        print()
        print("To debug this, run 'tox -e py36-pyqt59-cov' "
              "(or py35-pyqt59-cov) locally and check htmlcov/index.html")
        print("or check https://codecov.io/github/qutebrowser/qutebrowser")
        print()

    if 'CI' in os.environ:
        print("Keeping coverage.xml on CI.")
    else:
        os.remove('coverage.xml')
    return 1 if messages else 0


def main_check_all():
    """Check the coverage for all files individually.

    This makes sure the files have 100% coverage without running unrelated
    tests.

    This runs pytest with the used executable, so check_coverage.py should be
    called with something like ./.tox/py36/bin/python.
    """
    for test_file, src_file in PERFECT_FILES:
        if test_file is None:
            continue
        subprocess.run(
            [sys.executable, '-m', 'pytest', '--cov', 'qutebrowser',
             '--cov-report', 'xml', test_file], check=True)
        with open('coverage.xml', encoding='utf-8') as f:
            messages = check(f, [(test_file, src_file)])
        os.remove('coverage.xml')

        messages = [msg for msg in messages
                    if msg.typ == MsgType.insufficent_coverage]
        if messages:
            for msg in messages:
                print(msg.text)
            return 1
        else:
            print("Check ok!")
    return 0


def main():
    scriptutils.change_cwd()
    if '--check-all' in sys.argv:
        return main_check_all()
    else:
        return main_check()


if __name__ == '__main__':
    sys.exit(main())
