"""A vim like browser based on Qt.

Files:
    __init__.py      - This file.
    __main__.py      - Entry point for qutebrowser, to use\
                       'python -m qutebrowser'.
    app.py           - Main qutebrowser application>
    simplebrowser.py - Simple browser for testing purposes.

Subpackages:
    commands - Handling of commands and key parsing.
    utils    - Misc utility code.
    widgets  - Qt widgets displayed on the screen.
"""

__version_info__ = (0, 0, 0)
__version__ = '.'.join(map(str, __version_info__))
