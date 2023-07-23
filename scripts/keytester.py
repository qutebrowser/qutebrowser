#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Small test script to show key presses.

Use python3 -m scripts.keytester to launch it.
"""

from qutebrowser.qt.widgets import QApplication
from qutebrowser.misc import miscwidgets

app = QApplication([])
w = miscwidgets.KeyTesterWidget()
w.show()
app.exec()
