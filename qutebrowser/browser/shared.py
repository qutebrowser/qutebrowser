# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Various utilities shared between webpage/webview subclasses."""

import os
import sys
import html
import enum
import netrc
import tempfile
from typing import Callable, Mapping, List, Optional, Iterable, Iterator

from qutebrowser.qt.core import QUrl, pyqtBoundSignal

from qutebrowser.config import config
from qutebrowser.utils import (usertypes, message, log, objreg, jinja, utils,
                               qtutils, version, urlutils)
from qutebrowser.mainwindow import mainwindow
from qutebrowser.misc import guiprocess, objects


class CallSuper(Exception):
    """Raised when the caller should call the superclass instead."""


def custom_headers(url):
    """Get the combined custom headers."""
    headers = {}

    dnt_config = config.instance.get('content.headers.do_not_track', url=url)
    if dnt_config is not None:
        dnt = b'1' if dnt_config else b'0'
        headers[b'DNT'] = dnt

    conf_headers = config.instance.get('content.headers.custom', url=url)
    for header, value in conf_headers.items():
        encoded_header = header.encode('ascii')
        encoded_value = b"" if value is None else value.encode('ascii')
        headers[encoded_header] = encoded_value

    accept_language = config.instance.get('content.headers.accept_language',
                                          url=url)
    if accept_language is not None:
        headers[b'Accept-Language'] = accept_language.encode('ascii')

    return sorted(headers.items())


def authentication_required(url, authenticator, abort_on):
    """Ask a prompt for an authentication question."""
    realm = authenticator.realm()
    if realm:
        msg = '<b>{}</b> says:<br/>{}'.format(
            html.escape(url.toDisplayString()), html.escape(realm))
    else:
        msg = '<b>{}</b> needs authentication'.format(
            html.escape(url.toDisplayString()))
    urlstr = url.toString(QUrl.UrlFormattingOption.RemovePassword | QUrl.ComponentFormattingOption.FullyEncoded)
    answer = message.ask(title="Authentication required", text=msg,
                         mode=usertypes.PromptMode.user_pwd,
                         abort_on=abort_on, url=urlstr)
    if answer is not None:
        authenticator.setUser(answer.user)
        authenticator.setPassword(answer.password)
    return answer


def _format_msg(msg: str) -> str:
    """Convert message to HTML suitable for rendering."""
    return html.escape(msg).replace('\n', '<br />')


def javascript_confirm(url, js_msg, abort_on):
    """Display a javascript confirm prompt."""
    log.js.debug("confirm: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper

    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          _format_msg(js_msg))
    urlstr = url.toString(QUrl.UrlFormattingOption.RemovePassword | QUrl.ComponentFormattingOption.FullyEncoded)
    ans = message.ask('Javascript confirm', msg,
                      mode=usertypes.PromptMode.yesno,
                      abort_on=abort_on, url=urlstr)
    return bool(ans)


def javascript_prompt(url, js_msg, default, abort_on):
    """Display a javascript prompt."""
    log.js.debug("prompt: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper
    if not config.val.content.javascript.prompt:
        return (False, "")

    msg = '<b>{}</b> asks:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          _format_msg(js_msg))
    urlstr = url.toString(QUrl.UrlFormattingOption.RemovePassword | QUrl.ComponentFormattingOption.FullyEncoded)
    answer = message.ask('Javascript prompt', msg,
                         mode=usertypes.PromptMode.text,
                         default=default,
                         abort_on=abort_on, url=urlstr)

    if answer is None:
        return (False, "")
    else:
        return (True, answer)


def javascript_alert(url, js_msg, abort_on):
    """Display a javascript alert."""
    log.js.debug("alert: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper

    if not config.val.content.javascript.alert:
        return

    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          _format_msg(js_msg))
    urlstr = url.toString(QUrl.UrlFormattingOption.RemovePassword | QUrl.ComponentFormattingOption.FullyEncoded)
    message.ask('Javascript alert', msg, mode=usertypes.PromptMode.alert,
                abort_on=abort_on, url=urlstr)


# Needs to line up with the values allowed for the
# content.javascript.log setting.
_JS_LOGMAP: Mapping[str, Callable[[str], None]] = {
    'none': lambda arg: None,
    'debug': log.js.debug,
    'info': log.js.info,
    'warning': log.js.warning,
    'error': log.js.error,
}
# Callables to use for content.javascript.log_message.
# Note that the keys are JS log levels here, not config settings!
_JS_LOGMAP_MESSAGE: Mapping[usertypes.JsLogLevel, Callable[[str], None]] = {
    usertypes.JsLogLevel.info: message.info,
    usertypes.JsLogLevel.warning: message.warning,
    usertypes.JsLogLevel.error: message.error,
}


def _js_log_to_ui(
    level: usertypes.JsLogLevel,
    source: str,
    line: int,
    msg: str,
) -> bool:
    """Log a JS message to the UI, if configured accordingly.

    Returns:
        True if the log message has been shown as a qutebrowser message,
        False otherwise.
    """
    logstring = f"[{source}:{line}] {msg}"
    message_levels = config.cache['content.javascript.log_message.levels']
    message_excludes = config.cache['content.javascript.log_message.excludes']

    match = utils.match_globs(message_levels, source)
    if match is None:
        return False
    if level.name not in message_levels[match]:
        return False

    exclude_match = utils.match_globs(message_excludes, source)
    if exclude_match is not None:
        if utils.match_globs(message_excludes[exclude_match], msg) is not None:
            return False

    func = _JS_LOGMAP_MESSAGE[level]
    func(f"JS: {logstring}")
    return True


def javascript_log_message(
    level: usertypes.JsLogLevel,
    source: str,
    line: int,
    msg: str,
) -> None:
    """Display a JavaScript log message."""
    if _js_log_to_ui(level=level, source=source, line=line, msg=msg):
        return

    logstring = f"[{source}:{line}] {msg}"
    logger = _JS_LOGMAP[config.cache['content.javascript.log'][level.name]]
    logger(logstring)


def handle_certificate_error(
        *,
        request_url: QUrl,
        first_party_url: QUrl,
        error: usertypes.AbstractCertificateErrorWrapper,
        abort_on: Iterable[pyqtBoundSignal],
) -> None:
    """Display a certificate error question.

    Args:
        request_url: The URL of the request where the errors happened.
        first_party_url: The URL of the page we're visiting. Might be an invalid QUrl.
        error: A single error.
        abort_on: Signals aborting a question.
    """
    conf = config.instance.get('content.tls.certificate_errors', url=request_url)
    log.network.debug(f"Certificate error {error!r}, config {conf}")

    assert error.is_overridable(), repr(error)

    # We get the first party URL with a heuristic - with HTTP -> HTTPS redirects, the
    # scheme might not match.
    is_resource = (
        first_party_url.isValid() and
        not request_url.matches(first_party_url, urlutils.FormatOption.REMOVE_SCHEME))

    if conf == 'ask' or conf == 'ask-block-thirdparty' and not is_resource:
        err_template = jinja.environment.from_string("""
            {% if is_resource %}
            <p>
                Error while loading resource <b>{{request_url.toDisplayString()}}</b><br/>
                on page <b>{{first_party_url.toDisplayString()}}</b>:
            </p>
            {% else %}
            <p>Error while loading page <b>{{request_url.toDisplayString()}}</b>:</p>
            {% endif %}

            {{error.html()|safe}}

            {% if is_resource %}
            <p><i>Consider reporting this to the website operator, or set
            <tt>content.tls.certificate_errors</tt> to <tt>ask-block-thirdparty</tt> to
            always block invalid resource loads.</i></p>
            {% endif %}

            Do you want to ignore these errors and continue loading the page <b>insecurely</b>?
        """.strip())
        msg = err_template.render(
            request_url=request_url,
            first_party_url=first_party_url,
            is_resource=is_resource,
            error=error,
        )
        urlstr = request_url.toString(
            urlutils.FormatOption.REMOVE_PASSWORD | urlutils.FormatOption.ENCODED)
        title = "Certificate error"

        try:
            error.defer()
        except usertypes.UndeferrableError:
            # QtNetwork / QtWebKit and buggy PyQt versions
            # Show blocking question prompt
            ignore = message.ask(title=title, text=msg,
                                 mode=usertypes.PromptMode.yesno, default=False,
                                 abort_on=abort_on, url=urlstr)
            if ignore:
                error.accept_certificate()
            else:  # includes None, i.e. prompt aborted
                error.reject_certificate()
        else:
            # Show non-blocking question prompt
            message.confirm_async(
                title=title,
                text=msg,
                abort_on=abort_on,
                url=urlstr,
                yes_action=error.accept_certificate,
                no_action=error.reject_certificate,
                cancel_action=error.reject_certificate,
            )
    elif conf == 'load-insecurely':
        message.error(f'Certificate error: {error}')
        error.accept_certificate()
    elif conf == 'block':
        error.reject_certificate()
    elif conf == 'ask-block-thirdparty' and is_resource:
        log.network.error(
            f"Certificate error in resource load: {error}\n"
            f"  request URL:     {request_url.toDisplayString()}\n"
            f"  first party URL: {first_party_url.toDisplayString()}")
        error.reject_certificate()
    else:
        raise utils.Unreachable(conf, is_resource)


def feature_permission(url, option, msg, yes_action, no_action, abort_on,
                       blocking=False):
    """Handle a feature permission request.

    Args:
        url: The URL the request was done for.
        option: An option name to check.
        msg: A string like "show notifications"
        yes_action: A callable to call if the request was approved
        no_action: A callable to call if the request was denied
        abort_on: A list of signals which interrupt the question.
        blocking: If True, ask a blocking question.

    Return:
        The Question object if a question was asked (and blocking=False),
        None otherwise.
    """
    config_val = config.instance.get(option, url=url)
    if config_val == 'ask':
        if url.isValid():
            urlstr = url.toString(QUrl.UrlFormattingOption.RemovePassword | QUrl.ComponentFormattingOption.FullyEncoded)
            text = "Allow the website at <b>{}</b> to {}?".format(
                html.escape(url.toDisplayString()), msg)
        else:
            urlstr = None
            option = None  # For message.ask/confirm_async
            text = "Allow the website to {}?".format(msg)

        if blocking:
            answer = message.ask(abort_on=abort_on, title='Permission request',
                                 text=text, url=urlstr, option=option,
                                 mode=usertypes.PromptMode.yesno)
            if answer:
                yes_action()
            else:
                no_action()
            return None
        else:
            return message.confirm_async(
                yes_action=yes_action, no_action=no_action,
                cancel_action=no_action, abort_on=abort_on,
                title='Permission request', text=text, url=urlstr,
                option=option)
    elif config_val:
        yes_action()
        return None
    else:
        no_action()
        return None


def get_tab(win_id, target):
    """Get a tab widget for the given usertypes.ClickTarget.

    Args:
        win_id: The window ID to open new tabs in
        target: A usertypes.ClickTarget
    """
    tabbed_browser = objreg.get('tabbed-browser', scope='window', window=win_id)
    if target == usertypes.ClickTarget.window:
        window = mainwindow.MainWindow(private=tabbed_browser.is_private)
        tab = window.tabbed_browser.tabopen(url=None, background=False)
        window.show()
        return tab
    elif target in [usertypes.ClickTarget.tab, usertypes.ClickTarget.tab_bg]:
        return tabbed_browser.tabopen(
            url=None,
            background=target == usertypes.ClickTarget.tab_bg,
        )

    raise ValueError(f"Invalid ClickTarget {target}")


def get_user_stylesheet(searching=False):
    """Get the combined user-stylesheet."""
    css = ''
    stylesheets = config.val.content.user_stylesheets

    for filename in stylesheets:
        with open(filename, 'r', encoding='utf-8') as f:
            css += f.read()

    setting = config.val.scrolling.bar
    if setting == 'overlay' and utils.is_mac:
        setting = 'when-searching'

    if setting == 'never' or setting == 'when-searching' and not searching:
        css += '\nhtml > ::-webkit-scrollbar { width: 0px; height: 0px; }'

    if (objects.backend == usertypes.Backend.QtWebEngine and
            version.qtwebengine_versions().chromium_major in [87, 90] and
            config.val.colors.webpage.darkmode.enabled and
            config.val.colors.webpage.darkmode.policy.images == 'smart' and
            config.val.content.site_specific_quirks.enabled and
            'misc-mathml-darkmode' not in config.val.content.site_specific_quirks.skip):
        # WORKAROUND for MathML-output on Wikipedia being black on black.
        # See https://bugs.chromium.org/p/chromium/issues/detail?id=1126606
        css += ('\nimg.mwe-math-fallback-image-inline, '
                'img.mwe-math-fallback-image-display { filter: invert(100%); }')

    return css


def netrc_authentication(url, authenticator):
    """Perform authorization using netrc.

    Args:
        url: The URL the request was done for.
        authenticator: QAuthenticator object used to set credentials provided.

    Return:
        True if netrc found credentials for the URL.
        False otherwise.
    """
    if 'HOME' not in os.environ:
        # We'll get an OSError by netrc if 'HOME' isn't available in
        # os.environ. We don't want to log that, so we prevent it
        # altogether.
        return False

    user = None
    password = None
    authenticators = None

    try:
        net = netrc.netrc(config.val.content.netrc_file)

        if url.port() != -1:
            authenticators = net.authenticators(
                "{}:{}".format(url.host(), url.port()))

        if not authenticators:
            authenticators = net.authenticators(url.host())

        if authenticators:
            user, _account, password = authenticators
    except FileNotFoundError:
        log.misc.debug("No .netrc file found")
    except OSError as e:
        log.misc.exception("Unable to read the netrc file: {}".format(e))
    except netrc.NetrcParseError as e:
        log.misc.exception("Error when parsing the netrc file: {}".format(e))

    if user is None:
        return False

    authenticator.setUser(user)
    authenticator.setPassword(password)

    return True


class FileSelectionMode(enum.Enum):
    """Mode to use for file selectors in choose_file."""

    single_file = enum.auto()
    multiple_files = enum.auto()
    folder = enum.auto()


def choose_file(qb_mode: FileSelectionMode) -> List[str]:
    """Select file(s)/folder for up-/downloading, using an external command.

    Args:
        qb_mode: File selection mode

    Return:
        A list of selected file paths, or empty list if no file is selected.
        If multiple is False, the return value will have at most 1 item.
    """
    command = {
        FileSelectionMode.single_file: config.val.fileselect.single_file.command,
        FileSelectionMode.multiple_files: config.val.fileselect.multiple_files.command,
        FileSelectionMode.folder: config.val.fileselect.folder.command,
    }[qb_mode]
    use_tmp_file = any('{}' in arg for arg in command[1:])
    if use_tmp_file:
        with tempfile.NamedTemporaryFile(
            prefix='qutebrowser-fileselect-',
            delete=False,
        ) as handle:
            tmpfilename = handle.name
        with utils.cleanup_file(tmpfilename):
            command = (
                command[:1] +
                [arg.replace('{}', tmpfilename) for arg in command[1:]]
            )
            return _execute_fileselect_command(
                command=command,
                qb_mode=qb_mode,
                tmpfilename=tmpfilename,
            )
    else:
        return _execute_fileselect_command(
            command=command,
            qb_mode=qb_mode,
        )


def _execute_fileselect_command(
    command: List[str],
    qb_mode: FileSelectionMode,
    tmpfilename: Optional[str] = None
) -> List[str]:
    """Execute external command to choose file.

    Args:
        qb_mode: Should selecting multiple files be allowed.
        tmpfilename: Path to the temporary file if used, otherwise None.

    Return:
        A list of selected file paths, or empty list if no file is selected.
        If multiple is False, the return value will have at most 1 item.
    """
    proc = guiprocess.GUIProcess(what='choose-file')
    proc.start(command[0], command[1:])

    loop = qtutils.EventLoop()
    proc.finished.connect(lambda _code, _status: loop.exit())
    loop.exec()

    if tmpfilename is None:
        selected_files = proc.stdout.splitlines()
    else:
        try:
            with open(tmpfilename, mode='r', encoding=sys.getfilesystemencoding()) as f:
                selected_files = f.read().splitlines()
        except OSError as e:
            message.error(f"Failed to open tempfile {tmpfilename} ({e})!")
            selected_files = []

    return list(_validated_selected_files(
        qb_mode=qb_mode, selected_files=selected_files))


def _validated_selected_files(
    qb_mode: FileSelectionMode,
    selected_files: List[str],
) -> Iterator[str]:
    """Validates selected files if they are.

        * Of correct type
        * Of correct number
        * Existent

    Args:
        qb_mode: File selection mode used
        selected_files: files selected

    Return:
        List of selected files that pass the checks.
    """
    if qb_mode != FileSelectionMode.multiple_files:
        if len(selected_files) > 1:
            message.warning("More than one file/folder chosen, using only the first")
            selected_files = selected_files[:1]
    for selected_file in selected_files:
        if not os.path.exists(selected_file):
            message.warning(f"Ignoring non-existent file '{selected_file}'")
            continue
        if qb_mode == FileSelectionMode.folder:
            if not os.path.isdir(selected_file):
                message.warning(
                    f"Expected folder but got file, ignoring '{selected_file}'"
                )
                continue
        else:
            # pylint: disable=else-if-used
            if not os.path.isfile(selected_file):
                message.warning(
                    f"Expected file but got folder, ignoring '{selected_file}'"
                )
                continue
        yield selected_file
