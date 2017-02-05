#!/usr/bin/env python3
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

"""Very simple browser for testing purposes."""

import sys
import argparse

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtWebKitWidgets import QWebView
except ImportError:
    QWebView = None

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


def parse_args():
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='The URL to open')
    parser.add_argument('--plugins', '-p', help='Enable plugins',
                        default=False, action='store_true')
    if QWebEngineView is not None:
        parser.add_argument('--webengine', help='Use QtWebEngine',
                            default=False, action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    app = QApplication(sys.argv)

    if QWebView is None and QWebEngineView is None:
        print("Found no suitable backend to run with!")
        sys.exit(1)
    elif QWebView is None and not args.webengine:
        print("Using QtWebEngine because QtWebKit is unavailable")
        wv = QWebEngineView()
        using_webengine = True
    elif args.webengine:
        if QWebEngineView is None:
            print("Requested QtWebEngine, but it could not be imported!")
            sys.exit(1)
        wv = QWebEngineView()
        using_webengine = True
    else:
        wv = QWebView()
        using_webengine = False

    wv.loadStarted.connect(lambda: print("Loading started"))
    wv.loadProgress.connect(lambda p: print("Loading progress: {}%".format(p)))
    wv.loadFinished.connect(lambda: print("Loading finished"))

    if args.plugins and not using_webengine:
        from PyQt5.QtWebKit import QWebSettings
        wv.settings().setAttribute(QWebSettings.PluginsEnabled, True)

    wv.load(QUrl.fromUserInput(args.url))
    wv.show()

    app.exec_()
