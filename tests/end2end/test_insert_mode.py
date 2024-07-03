# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test insert mode settings on html files."""

import pytest


@pytest.mark.parametrize('file_name, elem_id, source, input_text', [
    ('textarea.html', 'qute-textarea', 'clipboard', 'qutebrowser'),
    ('textarea.html', 'qute-textarea', 'keypress', 'superqutebrowser'),
    ('input.html', 'qute-input', 'clipboard', 'amazingqutebrowser'),
    ('input.html', 'qute-input', 'keypress', 'awesomequtebrowser'),
    pytest.param('autofocus.html', 'qute-input-autofocus', 'keypress',
                 'cutebrowser', marks=pytest.mark.flaky),
])
@pytest.mark.parametrize('zoom', [100, 125, 250])
def test_insert_mode(file_name, elem_id, source, input_text, zoom,
                     quteproc, request):
    url_path = 'data/insert_mode_settings/html/{}'.format(file_name)
    quteproc.open_path(url_path)
    quteproc.send_cmd(':zoom {}'.format(zoom))

    quteproc.send_cmd(':click-element --force-event id {}'.format(elem_id))
    quteproc.wait_for(message='Entering mode KeyMode.insert (reason: *)')
    quteproc.send_cmd(':debug-set-fake-clipboard')

    if source == 'keypress':
        quteproc.press_keys(input_text)
    elif source == 'clipboard':
        quteproc.send_cmd(':debug-set-fake-clipboard "{}"'.format(input_text))
        quteproc.send_cmd(':insert-text {clipboard}')
    else:
        raise ValueError("Invalid source {!r}".format(source))

    quteproc.wait_for_js('contents: {}'.format(input_text))
    quteproc.send_cmd(':mode-leave')


@pytest.mark.parametrize('auto_load, background, insert_mode', [
    (False, False, False),  # auto_load disabled
    (True, False, True),  # enabled and foreground tab
    (True, True, False),  # background tab
])
def test_auto_load(quteproc, auto_load, background, insert_mode):
    quteproc.set_setting('input.insert_mode.auto_load', str(auto_load))
    url_path = 'data/insert_mode_settings/html/autofocus.html'
    quteproc.open_path(url_path, new_bg_tab=background)

    log_message = 'Entering mode KeyMode.insert (reason: *)'
    if insert_mode:
        quteproc.wait_for(message=log_message)
        quteproc.send_cmd(':mode-leave')
    else:
        quteproc.ensure_not_logged(message=log_message)


def test_auto_leave_insert_mode(quteproc):
    url_path = 'data/insert_mode_settings/html/autofocus.html'
    quteproc.open_path(url_path)

    quteproc.set_setting('input.insert_mode.auto_leave', 'true')
    quteproc.send_cmd(':zoom 100')

    quteproc.press_keys('abcd')

    quteproc.send_cmd(':hint all')
    quteproc.wait_for(message='hints: *')

    # Select the disabled input box to leave insert mode
    quteproc.send_cmd(':hint-follow s')
    quteproc.wait_for(message='Clicked non-editable element!')


@pytest.mark.parametrize('leave_on_load', [True, False])
def test_auto_leave_insert_mode_reload(quteproc, leave_on_load):
    url_path = 'data/hello.txt'
    quteproc.open_path(url_path)

    quteproc.set_setting('input.insert_mode.leave_on_load',
                         str(leave_on_load).lower())
    quteproc.send_cmd(':mode-enter insert')
    quteproc.wait_for(message='Entering mode KeyMode.insert (reason: *)')
    quteproc.send_cmd(':reload')
    if leave_on_load:
        quteproc.wait_for(message='Leaving mode KeyMode.insert (reason: *)')
    else:
        quteproc.wait_for(
            message='Ignoring leave_on_load request due to setting.')
