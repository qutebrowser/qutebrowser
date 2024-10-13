# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# To allow count being documented
# pylint: disable=differing-param-doc

"""Various commands."""

import os
import signal
import logging
import pathlib
from typing import Optional
from collections.abc import Sequence, Callable

try:
    import hunter
except ImportError:
    hunter = None

from qutebrowser.qt.core import Qt
from qutebrowser.qt.printsupport import QPrintPreviewDialog

from qutebrowser.api import cmdutils, apitypes, message, config

# FIXME should be part of qutebrowser.api?
from qutebrowser.completion.models import miscmodels
from qutebrowser.utils import utils


_LOGGER = logging.getLogger('misc')


@cmdutils.register(name='reload')
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
def reloadpage(tab: Optional[apitypes.Tab],
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
def stop(tab: Optional[apitypes.Tab]) -> None:
    """Stop loading in the current/[count]th tab.

    Args:
        count: The tab index to stop, or None.
    """
    if tab is not None:
        tab.stop()


def _print_preview(tab: apitypes.Tab) -> None:
    """Show a print preview."""
    tab.printing.check_preview_support()
    diag = QPrintPreviewDialog(tab)
    diag.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    diag.setWindowFlags(
        diag.windowFlags() |
        Qt.WindowType.WindowMaximizeButtonHint |
        Qt.WindowType.WindowMinimizeButtonHint)
    diag.paintRequested.connect(tab.printing.to_printer)
    diag.exec()


def _print_pdf(tab: apitypes.Tab, path: pathlib.Path) -> None:
    """Print to the given PDF file."""
    tab.printing.check_pdf_support()
    path = path.expanduser()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise cmdutils.CommandError(e)

    tab.printing.to_pdf(path)
    _LOGGER.debug(f"Print to file: {path}")


@cmdutils.register(name='print')
@cmdutils.argument('tab', value=cmdutils.Value.count_tab)
@cmdutils.argument('pdf', flag='f', metavar='file')
def printpage(tab: Optional[apitypes.Tab],
              preview: bool = False, *,
              pdf: Optional[pathlib.Path] = None) -> None:
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


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def screenshot(
        tab: apitypes.Tab,
        filename: pathlib.Path,
        *,
        rect: str = None,
        force: bool = False,
) -> None:
    """Take a screenshot of the currently shown part of the page.

    The file format is automatically determined based on the given file extension.

    Args:
        filename: The file to save the screenshot to (~ gets expanded).
        rect: The rectangle to save, as a string like WxH+X+Y.
        force: Overwrite existing files.
    """
    expanded = filename.expanduser()
    if expanded.exists() and not force:
        raise cmdutils.CommandError(
            f"File {filename} already exists (use --force to overwrite)")

    try:
        qrect = None if rect is None else utils.parse_rect(rect)
    except ValueError as e:
        raise cmdutils.CommandError(str(e))

    pic = tab.grab_pixmap(qrect)
    if pic is None:
        raise cmdutils.CommandError("Getting screenshot failed")

    ok = pic.save(str(expanded))
    if not ok:
        raise cmdutils.CommandError(f"Saving to {filename} failed")

    _LOGGER.debug(f"Screenshot saved to {filename}")


@cmdutils.register(maxsplit=0)
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def insert_text(tab: apitypes.Tab, text: str) -> None:
    """Insert text at cursor position.

    Args:
        text: The text to insert.
    """
    def _insert_text_cb(elem: Optional[apitypes.WebElement]) -> None:
        if elem is None:
            message.error("No element focused!")
            return
        try:
            elem.insert_text(text)
        except apitypes.WebElemError as e:
            message.error(str(e))
            return

    tab.elements.find_focused(_insert_text_cb)


def _wrap_find_at_pos(value: str, tab: apitypes.Tab,
                      callback: Callable[[Optional[apitypes.WebElement]], None]
                      ) -> None:
    try:
        point = utils.parse_point(value)
    except ValueError as e:
        message.error(str(e))
        return
    tab.elements.find_at_pos(point, callback)


_FILTER_ERRORS = {
    'id': lambda x: f'with ID "{x}"',
    'css': lambda x: f'matching CSS selector "{x}"',
    'focused': lambda _: 'with focus',
    'position': lambda x: 'at position {x}',
}


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('filter_', choices=['id', 'css', 'position', 'focused'])
def click_element(tab: apitypes.Tab, filter_: str, value: str = None, *,  # noqa: C901
                  target: apitypes.ClickTarget =
                  apitypes.ClickTarget.normal,
                  force_event: bool = False,
                  select_first: bool = False) -> None:
    """Click the element matching the given filter.

    The given filter needs to result in exactly one element, otherwise, an
    error is shown.

    Args:
        filter_: How to filter the elements.

            - id: Get an element based on its ID.
            - css: Filter by a CSS selector.
            - position: Click the element at specified position.
               Specify `value` as 'x,y'.
            - focused: Click the currently focused element.
        value: The value to filter for. Optional for 'focused' filter.
        target: How to open the clicked element (normal/tab/tab-bg/window).
        force_event: Force generating a fake click event.
        select_first: Select first matching element if there are multiple.
    """
    def do_click(elem: apitypes.WebElement) -> None:
        try:
            elem.click(target, force_event=force_event)
        except apitypes.WebElemError as e:
            message.error(str(e))

    def single_cb(elem: Optional[apitypes.WebElement]) -> None:
        """Click a single element."""
        if elem is None:
            message.error(f"No element found {_FILTER_ERRORS[filter_](value)}!")
            return

        do_click(elem)

    def multiple_cb(elems: Sequence[apitypes.WebElement]) -> None:
        if not elems:
            message.error(f"No element found {_FILTER_ERRORS[filter_](value)}!")
            return

        if not select_first and len(elems) > 1:
            message.error(f"Multiple elements found {_FILTER_ERRORS[filter_](value)}!")
            return

        do_click(elems[0])

    if value is None and filter_ != 'focused':
        raise cmdutils.CommandError("Argument 'value' is only "
                                    "optional with filter 'focused'!")

    if filter_ == "id":
        assert value is not None
        tab.elements.find_id(elem_id=value, callback=single_cb)
    elif filter_ == "css":
        assert value is not None
        tab.elements.find_css(
            value,
            callback=multiple_cb,
            error_cb=lambda exc: message.error(str(exc)),
        )
    elif filter_ == "position":
        assert value is not None
        _wrap_find_at_pos(value, tab=tab, callback=single_cb)
    elif filter_ == "focused":
        tab.elements.find_focused(callback=single_cb)
    else:
        raise utils.Unreachable(filter_)


@cmdutils.register(debug=True)
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def debug_webaction(tab: apitypes.Tab, action: str, count: int = 1) -> None:
    """Execute a webaction.

    Available actions:
    https://doc.qt.io/archives/qt-5.5/qwebpage.html#WebAction-enum (WebKit)
    https://doc.qt.io/qt-6/qwebenginepage.html#WebAction-enum (WebEngine)

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
def tab_mute(tab: Optional[apitypes.Tab]) -> None:
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
def message_error(text: str, rich: bool = False) -> None:
    """Show an error message in the statusbar.

    Args:
        text: The text to show.
        rich: Render the given text as
              https://doc.qt.io/qt-6/richtext-html-subset.html[Qt Rich Text].
    """
    message.error(text, rich=rich)


@cmdutils.register()
@cmdutils.argument('count', value=cmdutils.Value.count)
def message_info(text: str, count: int = 1, rich: bool = False) -> None:
    """Show an info message in the statusbar.

    Args:
        text: The text to show.
        count: How many times to show the message.
        rich: Render the given text as
              https://doc.qt.io/qt-6/richtext-html-subset.html[Qt Rich Text].
    """
    for _ in range(count):
        message.info(text, rich=rich)


@cmdutils.register()
def message_warning(text: str, rich: bool = False) -> None:
    """Show a warning message in the statusbar.

    Args:
        text: The text to show.
        rich: Render the given text as
              https://doc.qt.io/qt-6/richtext-html-subset.html[Qt Rich Text].
    """
    message.warning(text, rich=rich)


@cmdutils.register(debug=True)
@cmdutils.argument('typ', choices=['exception', 'segfault'])
def debug_crash(typ: str = 'exception') -> None:
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.
    """
    # pylint: disable=broad-exception-raised
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


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('position', completion=miscmodels.inspector_position)
def devtools(tab: apitypes.Tab,
             position: apitypes.InspectorPosition = None) -> None:
    """Toggle the developer tools (web inspector).

    Args:
        position: Where to open the devtools
                  (right/left/top/bottom/window).
    """
    try:
        tab.private_api.toggle_inspector(position)
    except apitypes.InspectorError as e:
        raise cmdutils.CommandError(e)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def devtools_focus(tab: apitypes.Tab) -> None:
    """Toggle focus between the devtools/tab."""
    assert tab.data.splitter is not None
    try:
        tab.data.splitter.cycle_focus()
    except apitypes.InspectorError as e:
        raise cmdutils.CommandError(e)


@cmdutils.register(name='Ni!')
def knights_who_say_ni() -> None:
    """We are the Knights Who Say... 'Ni'!"""  # noqa: D400
    raise cmdutils.CommandError("Do you demand a shrubbery?")
