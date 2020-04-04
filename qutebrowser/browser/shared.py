# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various utilities shared between webpage/webview subclasses."""

import os
import html
import netrc
import typing

from PyQt5.QtCore import QUrl

from qutebrowser.config import config
from qutebrowser.utils import usertypes, message, log, objreg, jinja, utils
from qutebrowser.mainwindow import mainwindow


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
        headers[header.encode('ascii')] = value.encode('ascii')

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
    urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
    answer = message.ask(title="Authentication required", text=msg,
                         mode=usertypes.PromptMode.user_pwd,
                         abort_on=abort_on, url=urlstr)
    if answer is not None:
        authenticator.setUser(answer.user)
        authenticator.setPassword(answer.password)
    return answer


def javascript_confirm(url, js_msg, abort_on, *, escape_msg=True):
    """Display a javascript confirm prompt."""
    log.js.debug("confirm: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper

    js_msg = html.escape(js_msg) if escape_msg else js_msg
    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          js_msg)
    urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
    ans = message.ask('Javascript confirm', msg,
                      mode=usertypes.PromptMode.yesno,
                      abort_on=abort_on, url=urlstr)
    return bool(ans)


def javascript_prompt(url, js_msg, default, abort_on, *, escape_msg=True):
    """Display a javascript prompt."""
    log.js.debug("prompt: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper
    if not config.val.content.javascript.prompt:
        return (False, "")

    js_msg = html.escape(js_msg) if escape_msg else js_msg
    msg = '<b>{}</b> asks:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          js_msg)
    urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
    answer = message.ask('Javascript prompt', msg,
                         mode=usertypes.PromptMode.text,
                         default=default,
                         abort_on=abort_on, url=urlstr)

    if answer is None:
        return (False, "")
    else:
        return (True, answer)


def javascript_alert(url, js_msg, abort_on, *, escape_msg=True):
    """Display a javascript alert."""
    log.js.debug("alert: {}".format(js_msg))
    if config.val.content.javascript.modal_dialog:
        raise CallSuper

    if not config.val.content.javascript.alert:
        return

    js_msg = html.escape(js_msg) if escape_msg else js_msg
    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          js_msg)
    urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
    message.ask('Javascript alert', msg, mode=usertypes.PromptMode.alert,
                abort_on=abort_on, url=urlstr)


# Needs to line up with the values allowed for the
# content.javascript.log setting.
_JS_LOGMAP = {
    'none': lambda arg: None,
    'debug': log.js.debug,
    'info': log.js.info,
    'warning': log.js.warning,
    'error': log.js.error,
}  # type: typing.Mapping[str, typing.Callable[[str], None]]


def javascript_log_message(level, source, line, msg):
    """Display a JavaScript log message."""
    logstring = "[{}:{}] {}".format(source, line, msg)
    logger = _JS_LOGMAP[config.cache['content.javascript.log'][level.name]]
    logger(logstring)


def ignore_certificate_errors(url, errors, abort_on):
    """Display a certificate error question.

    Args:
        url: The URL the errors happened in
        errors: A list of QSslErrors or QWebEngineCertificateErrors

    Return:
        True if the error should be ignored, False otherwise.
    """
    ssl_strict = config.instance.get('content.ssl_strict', url=url)
    log.webview.debug("Certificate errors {!r}, strict {}".format(
        errors, ssl_strict))

    for error in errors:
        assert error.is_overridable(), repr(error)

    if ssl_strict == 'ask':
        err_template = jinja.environment.from_string("""
            Errors while loading <b>{{url.toDisplayString()}}</b>:<br/>
            <ul>
            {% for err in errors %}
                <li>{{err}}</li>
            {% endfor %}
            </ul>
        """.strip())
        msg = err_template.render(url=url, errors=errors)

        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        ignore = message.ask(title="Certificate errors - continue?", text=msg,
                             mode=usertypes.PromptMode.yesno, default=False,
                             abort_on=abort_on, url=urlstr)
        if ignore is None:
            # prompt aborted
            ignore = False
        return ignore
    elif ssl_strict is False:
        log.webview.debug("ssl_strict is False, only warning about errors")
        for err in errors:
            # FIXME we might want to use warn here (non-fatal error)
            # https://github.com/qutebrowser/qutebrowser/issues/114
            message.error('Certificate error: {}'.format(err))
        return True
    elif ssl_strict is True:
        return False
    else:
        raise ValueError("Invalid ssl_strict value {!r}".format(ssl_strict))
    raise utils.Unreachable


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
            urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
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
    if target == usertypes.ClickTarget.tab:
        bg_tab = False
    elif target == usertypes.ClickTarget.tab_bg:
        bg_tab = True
    elif target == usertypes.ClickTarget.window:
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        window = mainwindow.MainWindow(private=tabbed_browser.is_private)
        window.show()
        win_id = window.win_id
        bg_tab = False
    else:
        raise ValueError("Invalid ClickTarget {}".format(target))

    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    return tabbed_browser.tabopen(url=None, background=bg_tab)


def get_user_stylesheet(searching=False):
    """Get the combined user-stylesheet."""
    css = ''
    stylesheets = config.val.content.user_stylesheets

    for filename in stylesheets:
        with open(filename, 'r', encoding='utf-8') as f:
            css += f.read()

    if (config.val.scrolling.bar == 'never' or
            config.val.scrolling.bar == 'when-searching' and not searching):
        css += '\nhtml > ::-webkit-scrollbar { width: 0px; height: 0px; }'

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
