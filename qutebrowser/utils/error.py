# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tools related to error printing/displaying."""

from PyQt5.QtWidgets import QMessageBox

from qutebrowser.utils import log, utils


def _get_name(exc):
    """Get a suitable exception name as a string."""
    prefixes = ['qutebrowser', 'builtins']
    name = utils.qualname(exc.__class__)
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) + 1:]
            break
    return name


def handle_fatal_exc(exc, args, title, *, pre_text='', post_text=''):
    """Handle a fatal "expected" exception by displaying an error box.

    If --no-err-windows is given as argument, the text is logged to the error
    logger instead.

    Args:
        exc: The Exception object being handled.
        args: The argparser namespace.
        title: The title to be used for the error message.
        pre_text: The text to be displayed before the exception text.
        post_text: The text to be displayed after the exception text.
    """
    if args.no_err_windows:
        lines = [
            "Handling fatal {} with --no-err-windows!".format(_get_name(exc)),
            "",
            "title: {}".format(title),
            "pre_text: {}".format(pre_text),
            "post_text: {}".format(post_text),
            "exception text: {}".format(str(exc) or 'none'),
        ]
        log.misc.exception('\n'.join(lines))
    else:
        if pre_text:
            msg_text = '{}: {}'.format(pre_text, exc)
        else:
            msg_text = str(exc)
        if post_text:
            msg_text += '\n\n{}'.format(post_text)
        msgbox = QMessageBox(QMessageBox.Critical, title, msg_text)
        msgbox.exec_()
