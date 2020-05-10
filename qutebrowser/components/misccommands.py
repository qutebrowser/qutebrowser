# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various commands."""

import os
import signal
import functools
import logging
import typing

try:
    import hunter
except ImportError:
    hunter = None

from PyQt5.QtCore import Qt
from PyQt5.QtPrintSupport import QPrintPreviewDialog

from qutebrowser.api import cmdutils, apitypes, message, config


@cmdutils.register(name='reload')
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
def reloadpage(tab: typing.Optional[apitypes.Tab],
               force: bool = False) -> None:
    """Reload the current/[count]th tab.

    Args:
        count: The tab index to reload, or None.
        force: Bypass the page cache.
    """
    if tab is not None:
        tab.reload(force=force)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
def stop(tab: typing.Optional[apitypes.Tab]) -> None:
    """Stop loading in the current/[count]th tab.

    Args:
        count: The tab index to stop, or None.
    """
    if tab is not None:
        tab.stop()


def _print_preview(tab: apitypes.Tab) -> None:
    """Show a print preview."""
    def print_callback(ok: bool) -> None:
        if not ok:
            message.error("Printing failed!")

    tab.printing.check_preview_support()
    diag = QPrintPreviewDialog(tab)
    diag.setAttribute(Qt.WA_DeleteOnClose)
    diag.setWindowFlags(
        diag.windowFlags() |  # type: ignore[operator, arg-type]
        Qt.WindowMaximizeButtonHint |
        Qt.WindowMinimizeButtonHint)
    diag.paintRequested.connect(functools.partial(
        tab.printing.to_printer, callback=print_callback))
    diag.exec_()


def _print_pdf(tab: apitypes.Tab, filename: str) -> None:
    """Print to the given PDF file."""
    tab.printing.check_pdf_support()
    filename = os.path.expanduser(filename)
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.mkdir(directory)
    tab.printing.to_pdf(filename)
    logging.getLogger('misc').debug("Print to file: {}".format(filename))


@cmdutils.register(name='print')
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
@cmdutils.argument('pdf', flag='f', metavar='file')
def printpage(tab: typing.Optional[apitypes.Tab],
              preview: bool = False, *,
              pdf: str = None) -> None:
    """Print the current/[count]th tab.

    Args:
        preview: Show preview instead of printing.
        count: The tab index to print, or None.
        pdf: The file path to write the PDF to.
    """
    if tab is None:
        return

    try:
        if preview:
            _print_preview(tab)
        elif pdf:
            _print_pdf(tab, pdf)
        else:
            tab.printing.show_dialog()
    except apitypes.WebTabError as e:
        raise cmdutils.CommandError(e)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def home(tab: apitypes.Tab) -> None:
    """Open main startpage in current tab."""
    if tab.navigation_blocked():
        message.info("Tab is pinned!")
    else:
        tab.load_url(config.val.url.start_pages[0])


@cmdutils.register(debug=True)
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def debug_dump_page(tab: apitypes.Tab, dest: str, plain: bool = False) -> None:
    """Dump the current page's content to a file.

    Args:
        dest: Where to write the file to.
        plain: Write plain text instead of HTML.
    """
    dest = os.path.expanduser(dest)

    def callback(data: str) -> None:
        """Write the data to disk."""
        try:
            with open(dest, 'w', encoding='utf-8') as f:
                f.write(data)
        except OSError as e:
            message.error('Could not write page: {}'.format(e))
        else:
            message.info("Dumped page to {}.".format(dest))

    tab.dump_async(callback, plain=plain)


@cmdutils.register(maxsplit=0)
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def insert_text(tab: apitypes.Tab, text: str) -> None:
    """Insert text at cursor position.

    Args:
        text: The text to insert.
    """
    def _insert_text_cb(elem: typing.Optional[apitypes.WebElement]) -> None:
        if elem is None:
            message.error("No element focused!")
            return
        try:
            elem.insert_text(text)
        except apitypes.WebElemError as e:
            message.error(str(e))
            return

    tab.elements.find_focused(_insert_text_cb)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('filter_', choices=['id'])
def click_element(tab: apitypes.Tab, filter_: str, value: str, *,
                  target: apitypes.ClickTarget =
                  apitypes.ClickTarget.normal,
                  force_event: bool = False) -> None:
    """Click the element matching the given filter.

    The given filter needs to result in exactly one element, otherwise, an
    error is shown.

    Args:
        filter_: How to filter the elements.
                 id: Get an element based on its ID.
        value: The value to filter for.
        target: How to open the clicked element (normal/tab/tab-bg/window).
        force_event: Force generating a fake click event.
    """
    def single_cb(elem: typing.Optional[apitypes.WebElement]) -> None:
        """Click a single element."""
        if elem is None:
            message.error("No element found with id {}!".format(value))
            return
        try:
            elem.click(target, force_event=force_event)
        except apitypes.WebElemError as e:
            message.error(str(e))
            return

    handlers = {
        'id': (tab.elements.find_id, single_cb),
    }
    handler, callback = handlers[filter_]
    handler(value, callback)


@cmdutils.register(debug=True)
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def debug_webaction(tab: apitypes.Tab, action: str, count: int = 1) -> None:
    """Execute a webaction.

    Available actions:
    http://doc.qt.io/archives/qt-5.5/qwebpage.html#WebAction-enum (WebKit)
    http://doc.qt.io/qt-5/qwebenginepage.html#WebAction-enum (WebEngine)

    Args:
        action: The action to execute, e.g. MoveToNextChar.
        count: How many times to repeat the action.
    """
    for _ in range(count):
        try:
            tab.action.run_string(action)
        except apitypes.WebTabError as e:
            raise cmdutils.CommandError(str(e))


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
def tab_mute(tab: typing.Optional[apitypes.Tab]) -> None:
    """Mute/Unmute the current/[count]th tab.

    Args:
        count: The tab index to mute or unmute, or None
    """
    if tab is None:
        return
    try:
        tab.audio.set_muted(not tab.audio.is_muted(), override=True)
    except apitypes.WebTabError as e:
        raise cmdutils.CommandError(e)


@cmdutils.register()
def nop() -> None:
    """Do nothing."""


@cmdutils.register()
def message_error(text: str) -> None:
    """Show an error message in the statusbar.

    Args:
        text: The text to show.
    """
    message.error(text)


@cmdutils.register()
@cmdutils.argument('count', value=cmdutils.Value.count)
def message_info(text: str, count: int = 1) -> None:
    """Show an info message in the statusbar.

    Args:
        text: The text to show.
        count: How many times to show the message
    """
    for _ in range(count):
        message.info(text)


@cmdutils.register()
def message_warning(text: str) -> None:
    """Show a warning message in the statusbar.

    Args:
        text: The text to show.
    """
    message.warning(text)


@cmdutils.register(debug=True)
@cmdutils.argument('typ', choices=['exception', 'segfault'])
def debug_crash(typ: str = 'exception') -> None:
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.
    """
    if typ == 'segfault':
        os.kill(os.getpid(), signal.SIGSEGV)
        raise Exception("Segfault failed (wat.)")
    raise Exception("Forced crash")


@cmdutils.register(debug=True, maxsplit=0, no_cmd_split=True)
def debug_trace(expr: str = "") -> None:
    """Trace executed code via hunter.

    Args:
        expr: What to trace, passed to hunter.
    """
    if hunter is None:
        raise cmdutils.CommandError("You need to install 'hunter' to use this "
                                    "command!")
    try:
        eval('hunter.trace({})'.format(expr))
    except Exception as e:
        raise cmdutils.CommandError("{}: {}".format(e.__class__.__name__, e))
