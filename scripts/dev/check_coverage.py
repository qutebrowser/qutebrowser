#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import sys
import enum
import os.path
import subprocess
import collections

from xml.etree import ElementTree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

Message = collections.namedtuple('Message', 'typ, text')
MsgType = enum.Enum('MsgType', 'insufficent_coverage, perfect_file')


# A list of (test_file, tested_file) tuples. test_file can be None.
PERFECT_FILES = [
    (None,
        'qutebrowser/commands/cmdexc.py'),
    ('tests/unit/commands/test_cmdutils.py',
        'qutebrowser/commands/cmdutils.py'),
    ('tests/unit/commands/test_argparser.py',
        'qutebrowser/commands/argparser.py'),

    ('tests/unit/browser/webkit/test_cache.py',
        'qutebrowser/browser/webkit/cache.py'),
    ('tests/unit/browser/webkit/test_cookies.py',
        'qutebrowser/browser/webkit/cookies.py'),
    ('tests/unit/browser/webkit/test_history.py',
        'qutebrowser/browser/webkit/history.py'),
    ('tests/unit/browser/webkit/test_tabhistory.py',
        'qutebrowser/browser/webkit/tabhistory.py'),
    ('tests/unit/browser/webkit/http/test_http.py',
        'qutebrowser/browser/webkit/http.py'),
    ('tests/unit/browser/webkit/http/test_content_disposition.py',
        'qutebrowser/browser/webkit/rfc6266.py'),
    ('tests/unit/browser/webkit/test_webelem.py',
        'qutebrowser/browser/webkit/webelem.py'),
    ('tests/unit/browser/webkit/network/test_schemehandler.py',
        'qutebrowser/browser/webkit/network/schemehandler.py'),
    ('tests/unit/browser/webkit/network/test_filescheme.py',
        'qutebrowser/browser/webkit/network/filescheme.py'),
    ('tests/unit/browser/webkit/network/test_networkreply.py',
        'qutebrowser/browser/webkit/network/networkreply.py'),

    ('tests/unit/browser/test_signalfilter.py',
        'qutebrowser/browser/signalfilter.py'),
    # ('tests/unit/browser/test_tab.py',
    #     'qutebrowser/browser/tab.py'),

    ('tests/unit/keyinput/test_basekeyparser.py',
        'qutebrowser/keyinput/basekeyparser.py'),

    ('tests/unit/misc/test_autoupdate.py',
        'qutebrowser/misc/autoupdate.py'),
    ('tests/unit/misc/test_readline.py',
        'qutebrowser/misc/readline.py'),
    ('tests/unit/misc/test_split.py',
        'qutebrowser/misc/split.py'),
    ('tests/unit/misc/test_msgbox.py',
        'qutebrowser/misc/msgbox.py'),
    ('tests/unit/misc/test_checkpyver.py',
        'qutebrowser/misc/checkpyver.py'),
    ('tests/unit/misc/test_guiprocess.py',
        'qutebrowser/misc/guiprocess.py'),
    ('tests/unit/misc/test_editor.py',
        'qutebrowser/misc/editor.py'),
    ('tests/unit/misc/test_cmdhistory.py',
        'qutebrowser/misc/cmdhistory.py'),
    ('tests/unit/misc/test_ipc.py',
        'qutebrowser/misc/ipc.py'),
    ('tests/unit/misc/test_keyhints.py',
        'qutebrowser/misc/keyhintwidget.py'),
    ('tests/unit/misc/test_pastebin.py',
        'qutebrowser/misc/pastebin.py'),

    (None,
        'qutebrowser/mainwindow/statusbar/keystring.py'),
    ('tests/unit/mainwindow/statusbar/test_percentage.py',
        'qutebrowser/mainwindow/statusbar/percentage.py'),
    ('tests/unit/mainwindow/statusbar/test_progress.py',
        'qutebrowser/mainwindow/statusbar/progress.py'),
    ('tests/unit/mainwindow/statusbar/test_tabindex.py',
        'qutebrowser/mainwindow/statusbar/tabindex.py'),
    ('tests/unit/mainwindow/statusbar/test_textbase.py',
        'qutebrowser/mainwindow/statusbar/textbase.py'),
    ('tests/unit/mainwindow/statusbar/test_prompt.py',
        'qutebrowser/mainwindow/statusbar/prompt.py'),
    ('tests/unit/mainwindow/statusbar/test_url.py',
        'qutebrowser/mainwindow/statusbar/url.py'),

    ('tests/unit/config/test_configtypes.py',
        'qutebrowser/config/configtypes.py'),
    ('tests/unit/config/test_configdata.py',
        'qutebrowser/config/configdata.py'),
    ('tests/unit/config/test_configexc.py',
        'qutebrowser/config/configexc.py'),
    ('tests/unit/config/test_textwrapper.py',
        'qutebrowser/config/textwrapper.py'),
    ('tests/unit/config/test_style.py',
        'qutebrowser/config/style.py'),

    ('tests/unit/utils/test_qtutils.py',
        'qutebrowser/utils/qtutils.py'),
    ('tests/unit/utils/test_standarddir.py',
        'qutebrowser/utils/standarddir.py'),
    ('tests/unit/utils/test_urlutils.py',
        'qutebrowser/utils/urlutils.py'),
    ('tests/unit/utils/usertypes',
        'qutebrowser/utils/usertypes.py'),
    ('tests/unit/utils/test_utils.py',
        'qutebrowser/utils/utils.py'),
    ('tests/unit/utils/test_version.py',
        'qutebrowser/utils/version.py'),
    ('tests/unit/utils/test_debug.py',
        'qutebrowser/utils/debug.py'),
    ('tests/unit/utils/test_jinja.py',
        'qutebrowser/utils/jinja.py'),
    ('tests/unit/utils/test_error.py',
        'qutebrowser/utils/error.py'),
    ('tests/unit/utils/test_typing.py',
        'qutebrowser/utils/typing.py'),
    ('tests/unit/completion/test_models.py',
        'qutebrowser/completion/models/base.py'),

]


# 100% coverage because of end2end tests, but no perfect unit tests yet.
WHITELISTED_FILES = []


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

    return filename


def check(fileobj, perfect_files):
    """Main entry point which parses/checks coverage.xml if applicable."""
    if sys.platform != 'linux':
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
            text = "{} has {}% line and {}% branch coverage!".format(
                filename, line_cov, branch_cov)
            messages.append(Message(MsgType.insufficent_coverage, text))
        elif (filename not in perfect_src_files and not is_bad and
              filename not in WHITELISTED_FILES):
            text = ("{} has 100% coverage but is not in "
                    "perfect_files!".format(filename))
            messages.append(Message(MsgType.perfect_file, text))

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
        utils.print_title("Coverage check failed")
        for msg in messages:
            print(msg.text)
        print()
        print("You can run 'tox -e py35-cov' (or py34-cov) locally and check "
              "htmlcov/index.html to debug this.")
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

    This runs py.test with the used executable, so check_coverage.py should be
    called with something like ./.tox/py34/bin/python.
    """
    for test_file, src_file in PERFECT_FILES:
        if test_file is None:
            continue
        subprocess.check_call(
            [sys.executable, '-m', 'py.test', '--cov', 'qutebrowser',
             '--cov-report', 'xml', test_file])
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
    utils.change_cwd()
    if '--check-all' in sys.argv:
        return main_check_all()
    else:
        return main_check()


if __name__ == '__main__':
    sys.exit(main())
