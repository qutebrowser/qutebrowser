# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import html

import jinja2

from qutebrowser.config import config
from qutebrowser.utils import usertypes, message, log, objreg


class CallSuper(Exception):

    """Raised when the caller should call the superclass instead."""


def custom_headers():
    """Get the combined custom headers."""
    headers = {}
    dnt = b'1' if config.get('network', 'do-not-track') else b'0'
    headers[b'DNT'] = dnt
    headers[b'X-Do-Not-Track'] = dnt

    config_headers = config.get('network', 'custom-headers')
    if config_headers is not None:
        for header, value in config_headers.items():
            headers[header.encode('ascii')] = value.encode('ascii')

    accept_language = config.get('network', 'accept-language')
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
    answer = message.ask(title="Authentication required", text=msg,
                         mode=usertypes.PromptMode.user_pwd,
                         abort_on=abort_on)
    if answer is not None:
        authenticator.setUser(answer.user)
        authenticator.setPassword(answer.password)
    return answer


def javascript_confirm(url, js_msg, abort_on):
    """Display a javascript confirm prompt."""
    log.js.debug("confirm: {}".format(js_msg))
    if config.get('ui', 'modal-js-dialog'):
        raise CallSuper

    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          html.escape(js_msg))
    ans = message.ask('Javascript confirm', msg,
                      mode=usertypes.PromptMode.yesno,
                      abort_on=abort_on)
    return bool(ans)


def javascript_prompt(url, js_msg, default, abort_on):
    """Display a javascript prompt."""
    log.js.debug("prompt: {}".format(js_msg))
    if config.get('ui', 'modal-js-dialog'):
        raise CallSuper
    if config.get('content', 'ignore-javascript-prompt'):
        return (False, "")

    msg = '<b>{}</b> asks:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          html.escape(js_msg))
    answer = message.ask('Javascript prompt', msg,
                         mode=usertypes.PromptMode.text,
                         default=default,
                         abort_on=abort_on)

    if answer is None:
        return (False, "")
    else:
        return (True, answer)


def javascript_alert(url, js_msg, abort_on):
    """Display a javascript alert."""
    log.js.debug("alert: {}".format(js_msg))
    if config.get('ui', 'modal-js-dialog'):
        raise CallSuper

    if config.get('content', 'ignore-javascript-alert'):
        return

    msg = 'From <b>{}</b>:<br/>{}'.format(html.escape(url.toDisplayString()),
                                          html.escape(js_msg))
    message.ask('Javascript alert', msg, mode=usertypes.PromptMode.alert,
                abort_on=abort_on)


def ignore_certificate_errors(url, errors, abort_on):
    """Display a certificate error question.

    Args:
        url: The URL the errors happened in
        errors: A list of QSslErrors or QWebEngineCertificateErrors

    Return:
        True if the error should be ignored, False otherwise.
    """
    ssl_strict = config.get('network', 'ssl-strict')
    log.webview.debug("Certificate errors {!r}, strict {}".format(
        errors, ssl_strict))

    for error in errors:
        assert error.is_overridable(), repr(error)

    if ssl_strict == 'ask':
        err_template = jinja2.Template("""
            Errors while loading <b>{{url.toDisplayString()}}</b>:<br/>
            <ul>
            {% for err in errors %}
                <li>{{err}}</li>
            {% endfor %}
            </ul>
        """.strip())
        msg = err_template.render(url=url, errors=errors)

        ignore = message.ask(title="Certificate errors - continue?", text=msg,
                             mode=usertypes.PromptMode.yesno, default=False,
                             abort_on=abort_on)
        if ignore is None:
            # prompt aborted
            ignore = False
        return ignore
    elif ssl_strict is False:
        log.webview.debug("ssl-strict is False, only warning about errors")
        for err in errors:
            # FIXME we might want to use warn here (non-fatal error)
            # https://github.com/The-Compiler/qutebrowser/issues/114
            message.error('Certificate error: {}'.format(err))
        return True
    elif ssl_strict is True:
        return False
    else:
        raise ValueError("Invalid ssl_strict value {!r}".format(ssl_strict))
    raise AssertionError("Not reached")


def feature_permission(url, option, msg, yes_action, no_action, abort_on):
    """Handle a feature permission request.

    Args:
        url: The URL the request was done for.
        option: A (section, option) tuple for the option to check.
        msg: A string like "show notifications"
        yes_action: A callable to call if the request was approved
        no_action: A callable to call if the request was denied
        abort_on: A list of signals which interrupt the question.

    Return:
        The Question object if a question was asked, None otherwise.
    """
    config_val = config.get(*option)
    if config_val == 'ask':
        if url.isValid():
            text = "Allow the website at <b>{}</b> to {}?".format(
                html.escape(url.toDisplayString()), msg)
        else:
            text = "Allow the website to {}?".format(msg)

        return message.confirm_async(
            yes_action=yes_action, no_action=no_action,
            cancel_action=no_action, abort_on=abort_on,
            title='Permission request', text=text)
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
        win_id = win_id
        bg_tab = False
    elif target == usertypes.ClickTarget.tab_bg:
        win_id = win_id
        bg_tab = True
    elif target == usertypes.ClickTarget.window:
        from qutebrowser.mainwindow import mainwindow
        window = mainwindow.MainWindow()
        window.show()
        win_id = window.win_id
        bg_tab = False
    else:
        raise ValueError("Invalid ClickTarget {}".format(target))

    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    return tabbed_browser.tabopen(url=None, background=bg_tab)


def get_user_stylesheet():
    """Get the combined user-stylesheet."""
    filename = config.get('ui', 'user-stylesheet')

    if filename is None:
        css = ''
    else:
        with open(filename, 'r', encoding='utf-8') as f:
            css = f.read()

    if config.get('ui', 'hide-scrollbar'):
        css += '\nhtml > ::-webkit-scrollbar { width: 0px; height: 0px; }'

    return css
