"""Fixer to set QT_HARFBUZZ variable.

In its own file so it doesn't include any Qt stuff, because if it did, it
wouldn't work.
"""

import os
import sys


def fix():
    """Fix harfbuzz issues.

    This switches to an older (but more stable) harfbuzz font rendering engine
    instead of using the system wide one.

    This fixes crashes on various sites.
    See https://bugreports.qt-project.org/browse/QTBUG-36099
    """
    if sys.platform.startswith('linux'):
        # Switch to old but stable font rendering engine
        os.environ['QT_HARFBUZZ'] = 'old'
