#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tester for Qt segfaults with different harfbuzz engines."""

import os
import signal
import sys
import subprocess
import os.path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from scripts import utils


SCRIPT = """
import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKitWidgets import QWebView

def on_load_finished(ok):
    if ok:
        app.exit(0)
    else:
        app.exit(1)

app = QApplication([])
wv = QWebView()
wv.loadFinished.connect(on_load_finished)
wv.load(QUrl(sys.argv[1]))
#wv.show()
app.exec_()
"""


def print_ret(ret):
    """Print information about an exit status."""
    if ret == 0:
        utils.print_col("success", 'green')
    elif ret == -signal.SIGSEGV:
        utils.print_col("segfault", 'red')
    else:
        utils.print_col("error {}".format(ret), 'yellow')
    print()


def main():
    """Main entry point."""
    retvals = []
    if len(sys.argv) < 2:
        # pages which previously caused problems
        pages = [
            # ANGLE, https://bugreports.qt-project.org/browse/QTBUG-39723
            ('http://www.binpress.com/', False),
            ('http://david.li/flow/', False),
            ('https://imzdl.com/', False),
            # not reproducable
            # https://bugreports.qt-project.org/browse/QTBUG-39847
            ('http://www.20min.ch/', True),
            # HarfBuzz, https://bugreports.qt-project.org/browse/QTBUG-39278
            ('http://www.the-compiler.org/', True),
            ('http://phoronix.com', True),
            ('http://twitter.com', True),
            # HarfBuzz #2, https://bugreports.qt-project.org/browse/QTBUG-36099
            ('http://lenta.ru/', True),
            # Unknown, https://bugreports.qt-project.org/browse/QTBUG-41360
            ('http://salt.readthedocs.org/en/latest/topics/pillar/', True),
        ]
    else:
        pages = [(e, True) for e in sys.argv[1:]]
    for page, test_harfbuzz in pages:
        utils.print_bold("==== {} ====".format(page))
        if test_harfbuzz:
            print("With system harfbuzz:")
        ret = subprocess.call([sys.executable, '-c', SCRIPT, page])
        print_ret(ret)
        retvals.append(ret)
        if test_harfbuzz:
            print("With QT_HARFBUZZ=old:")
            env = dict(os.environ)
            env['QT_HARFBUZZ'] = 'old'
            ret = subprocess.call([sys.executable, '-c', SCRIPT, page],
                                  env=env)
            print_ret(ret)
            retvals.append(ret)
            print("With QT_HARFBUZZ=new:")
            env = dict(os.environ)
            env['QT_HARFBUZZ'] = 'new'
            ret = subprocess.call([sys.executable, '-c', SCRIPT, page],
                                  env=env)
            print_ret(ret)
            retvals.append(ret)
    if all(r == 0 for r in retvals):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
