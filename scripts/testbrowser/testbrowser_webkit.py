#!/usr/bin/env python3
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

"""Very simple browser for testing purposes."""

import sys
import argparse

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView


def parse_args():
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='The URL to open')
    parser.add_argument('--plugins', '-p', help='Enable plugins',
                        default=False, action='store_true')
    return parser.parse_known_args()[0]


if __name__ == '__main__':
    args = parse_args()
    app = QApplication(sys.argv)
    wv = QWebView()

    wv.loadStarted.connect(lambda: print("Loading started"))
    wv.loadProgress.connect(lambda p: print("Loading progress: {}%".format(p)))
    wv.loadFinished.connect(lambda: print("Loading finished"))

    if args.plugins:
        wv.settings().setAttribute(QWebSettings.PluginsEnabled, True)

    wv.load(QUrl.fromUserInput(args.url))
    wv.show()

    app.exec_()
