"""Entry point for qutebrowser. Simply execute qutebrowser."""

from qutebrowser.app import QuteBrowser
import sys

if __name__ == '__main__':
    app = QuteBrowser()
    sys.exit(app.exec_())
