#!/bin/bash

fd -g '*.py' -E 'qt' qutebrowser/ tests/ | xargs sed -i \
    -e 's/from PyQt5 import QtCore/from qutebrowser.qt import core as QtCore/' \
    -e 's/from PyQt5 import QtWebEngine/from qutebrowser.qt import webengine as QtWebEngine/' \
    -e 's/from PyQt5 import QtWebEngineWidgets/from qutebrowser.qt import webenginewidgets as QtWebEngineWidgets/' \
    -e 's/from PyQt5 import QtWebKit/from qutebrowser.qt import webkit as QtWebKit/' \
    -e 's/from PyQt5 import QtWebKitWidgets/from qutebrowser.qt import webkitwidgets as QtWebKitWidgets/' \
    -e 's/from PyQt5.QtCore/from qutebrowser.qt.core/' \
    -e 's/from PyQt5.QtGui/from qutebrowser.qt.gui/' \
    -e 's/from PyQt5.QtNetwork/from qutebrowser.qt.network/' \
    -e 's/from PyQt5.QtWebEngineCore/from qutebrowser.qt.webenginecore/' \
    -e 's/from PyQt5.QtWebEngineWidgets/from qutebrowser.qt.webenginewidgets/' \
    -e 's/from PyQt5.QtWebEngine/from qutebrowser.qt.webengine/' \
    -e 's/from PyQt5.QtWebKitWidgets/from qutebrowser.qt.webkitwidgets/' \
    -e 's/from PyQt5.QtWebKit/from qutebrowser.qt.webkit/' \
    -e 's/from PyQt5.QtWidgets/from qutebrowser.qt.widgets/' \
    -e 's/from PyQt5.QtPrintSupport/from qutebrowser.qt.printsupport/' \
    -e 's/from PyQt5.QtQml/from qutebrowser.qt.qml/' \
    -e 's/from PyQt5.QtSql/from qutebrowser.qt.sql/' \
    -e 's/from PyQt5.QtTest/from qutebrowser.qt.test/' \
    -e 's/from PyQt5.QtDBus/from qutebrowser.qt.dbus/'
