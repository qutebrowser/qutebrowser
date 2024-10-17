# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Module containing command managers (SearchRunner and CommandRunner)."""

import traceback
import re
import contextlib
from typing import TYPE_CHECKING
from collections.abc import Iterator, Mapping, MutableMapping, Callable

from qutebrowser.qt.core import pyqtSlot, QUrl, QObject

from qutebrowser.api import cmdutils
from qutebrowser.commands import cmdexc, parser
from qutebrowser.utils import message, objreg, qtutils, usertypes, utils, urlutils
from qutebrowser.keyinput import macros, modeman

if TYPE_CHECKING:
    from qutebrowser.mainwindow import tabbedbrowser
_ReplacementFunction = Callable[['tabbedbrowser.TabbedBrowser'], str]


last_command: dict[usertypes.KeyMode, tuple[str, int]] = {}


def _url(tabbed_browser):
    """Convenience method to get the current url."""
    try:
        return tabbed_browser.current_url()
    except qtutils.QtValueError as e:
        msg = "Current URL is invalid"
        if e.reason:
            msg += " ({})".format(e.reason)
        msg += "!"
        raise cmdutils.CommandError(msg)


def _init_variable_replacements() -> Mapping[str, _ReplacementFunction]:
    """Return a dict from variable replacements to fns processing them."""
    replacements: dict[str, _ReplacementFunction] = {
        'url': lambda tb: _url(tb).toString(
            QUrl.ComponentFormattingOption.FullyEncoded | QUrl.UrlFormattingOption.RemovePassword),
        'url:pretty': lambda tb: _url(tb).toString(
            QUrl.ComponentFormattingOption.DecodeReserved | QUrl.UrlFormattingOption.RemovePassword),
        'url:domain': lambda tb: "{}://{}{}".format(
            _url(tb).scheme(), _url(tb).host(),
            ":" + str(_url(tb).port()) if _url(tb).port() != -1 else ""),
        'url:auth': lambda tb: "{}:{}@".format(
            _url(tb).userName(),
            _url(tb).password()) if _url(tb).userName() else "",
        'url:scheme': lambda tb: _url(tb).scheme(),
        'url:username': lambda tb: _url(tb).userName(),
        'url:password': lambda tb: _url(tb).password(),
        'url:host': lambda tb: _url(tb).host(),
        'url:port': lambda tb: str(
            _url(tb).port()) if _url(tb).port() != -1 else "",
        'url:path': lambda tb: _url(tb).path(),
        'url:query': lambda tb: _url(tb).query(),
        'url:yank': lambda tb: urlutils.get_url_yank_text(_url(tb),
                                                          pretty=False),
        'title': lambda tb: tb.widget.page_title(tb.widget.currentIndex()),
        'clipboard': lambda _: utils.get_clipboard(),
        'primary': lambda _: utils.get_clipboard(selection=True),
    }

    for key in list(replacements):
        modified_key = '{' + key + '}'
        # x = modified_key is to avoid binding x as a closure
        replacements[modified_key] = (
            lambda _, x=modified_key: x)  # type: ignore[misc]
    return replacements


VARIABLE_REPLACEMENTS = _init_variable_replacements()
# A regex matching all variable replacements
VARIABLE_REPLACEMENT_PATTERN = re.compile(
    "{(?P<var>" + "|".join(VARIABLE_REPLACEMENTS.keys()) + ")}")


def replace_variables(win_id, arglist):
    """Utility function to replace variables like {url} in a list of args."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    values: MutableMapping[str, str] = {}
    args = []

    def repl_cb(matchobj):
        """Return replacement for given match."""
        var = matchobj.group("var")
        if var not in values:
            values[var] = VARIABLE_REPLACEMENTS[var](tabbed_browser)
        return values[var]

    try:
        for arg in arglist:
            # using re.sub with callback function replaces all variables in a
            # single pass and avoids expansion of nested variables (e.g.
            # "{url}" from clipboard is not expanded)
            args.append(VARIABLE_REPLACEMENT_PATTERN.sub(repl_cb, arg))
    except utils.ClipboardError as e:
        raise cmdutils.CommandError(e)
    return args


class AbstractCommandRunner(QObject):

    """Abstract base class for CommandRunner."""

    def run(self, text, count=None, *, safely=False):
        raise NotImplementedError

    @pyqtSlot(str, int)
    @pyqtSlot(str)
    def run_safely(self, text, count=None):
        """Run a command and display exceptions in the statusbar."""
        self.run(text, count, safely=True)


class CommandRunner(AbstractCommandRunner):

    """Parse and run qutebrowser commandline commands.

    Attributes:
        _win_id: The window this CommandRunner is associated with.
    """

    def __init__(self, win_id, partial_match=False, find_similar=True, parent=None):
        super().__init__(parent)
        self._parser = parser.CommandParser(
            partial_match=partial_match,
            find_similar=find_similar,
        )
        self._win_id = win_id

    @contextlib.contextmanager
    def _handle_error(self, safely: bool) -> Iterator[None]:
        """Show exceptions as errors if safely=True is given."""
        try:
            yield
        except cmdexc.Error as e:
            if safely:
                message.error(str(e), stack=traceback.format_exc())
            else:
                raise

    def run(self, text, count=None, *, safely=False):
        """Parse a command from a line of text and run it.

        Args:
            text: The text to parse.
            count: The count to pass to the command.
            safely: Show CmdError exceptions as messages.
        """
        record_last_command = True
        record_macro = True

        mode_manager = modeman.instance(self._win_id)
        cur_mode = mode_manager.mode

        parsed = None
        with self._handle_error(safely):
            parsed = self._parser.parse_all(text)

        if parsed is None:
            return  # type: ignore[unreachable]

        for result in parsed:
            with self._handle_error(safely):
                if result.cmd.no_replace_variables:
                    args = result.args
                else:
                    args = replace_variables(self._win_id, result.args)

                result.cmd.run(self._win_id, args, count=count)

            if result.cmdline[0] in ['repeat-command', 'cmd-repeat-last']:
                record_last_command = False

            if result.cmdline[0] in ['macro-record', 'macro-run', 'set-cmd-text', 'cmd-set-text']:
                record_macro = False

        if record_last_command:
            last_command[cur_mode] = (text, count)

        if record_macro and cur_mode == usertypes.KeyMode.normal:
            macros.macro_recorder.record_command(text, count)
