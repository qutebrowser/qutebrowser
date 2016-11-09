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

from qutebrowser.config import config
from qutebrowser.utils import usertypes, message, log


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
    msg = '<b>{}</b> says:<br/>{}'.format(
        html.escape(url.toDisplayString()),
        html.escape(authenticator.realm()))
    answer = message.ask(title="Authentication required", text=msg,
                         mode=usertypes.PromptMode.user_pwd,
                         abort_on=abort_on)
    if answer is not None:
        authenticator.setUser(answer.user)
        authenticator.setPassword(answer.password)


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
