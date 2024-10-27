# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tools related to error printing/displaying."""

from qutebrowser.qt.widgets import QMessageBox

from qutebrowser.utils import log, utils


def _get_name(exc: BaseException) -> str:
    """Get a suitable exception name as a string."""
    prefixes = ['qutebrowser.', 'builtins.']
    name = utils.qualname(exc.__class__)
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name.removeprefix(prefix)
            break
    return name


def handle_fatal_exc(exc: BaseException,
                     title: str, *,
                     no_err_windows: bool,
                     pre_text: str = '',
                     post_text: str = '') -> None:
    """Handle a fatal "expected" exception by displaying an error box.

    If --no-err-windows is given as argument, the text is logged to the error
    logger instead.

    Args:
        exc: The Exception object being handled.
        no_err_windows: Show text in log instead of error window.
        title: The title to be used for the error message.
        pre_text: The text to be displayed before the exception text.
        post_text: The text to be displayed after the exception text.
    """
    if no_err_windows:
        lines = [
            "Handling fatal {} with --no-err-windows!".format(_get_name(exc)),
            "",
            "title: {}".format(title),
            "pre_text: {}".format(pre_text),
            "post_text: {}".format(post_text),
            "exception text: {}".format(str(exc) or 'none'),
        ]
        log.misc.error('\n'.join(lines))
    else:
        log.misc.error("Fatal exception:")
        if pre_text:
            msg_text = '{}: {}'.format(pre_text, exc)
        else:
            msg_text = str(exc)
        if post_text:
            msg_text += '\n\n{}'.format(post_text)
        msgbox = QMessageBox(QMessageBox.Icon.Critical, title, msg_text)
        msgbox.exec()
