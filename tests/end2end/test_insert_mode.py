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

"""Test insert mode settings on html files."""

import pytest


@pytest.mark.parametrize(['file_name', 'elem_id', 'source', 'input_text'], [
    ('textarea.html', 'qute-textarea', 'clipboard', 'qutebrowser'),
    ('textarea.html', 'qute-textarea', 'keypress', 'superqutebrowser'),
    ('input.html', 'qute-input', 'clipboard', 'amazingqutebrowser'),
    ('input.html', 'qute-input', 'keypress', 'awesomequtebrowser'),
    ('autofocus.html', 'qute-input-autofocus', 'keypress', 'cutebrowser'),
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
    quteproc.send_cmd(':leave-mode')


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
        quteproc.send_cmd(':leave-mode')
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
    quteproc.send_cmd(':follow-hint s')
    quteproc.wait_for(message='Clicked non-editable element!')


@pytest.mark.parametrize('leave_on_load', [True, False])
def test_auto_leave_insert_mode_reload(quteproc, leave_on_load):
    url_path = 'data/hello.txt'
    quteproc.open_path(url_path)

    quteproc.set_setting('input.insert_mode.leave_on_load',
                         str(leave_on_load).lower())
    quteproc.send_cmd(':enter-mode insert')
    quteproc.wait_for(message='Entering mode KeyMode.insert (reason: *)')
    quteproc.send_cmd(':reload')
    if leave_on_load:
        quteproc.wait_for(message='Leaving mode KeyMode.insert (reason: *)')
    else:
        quteproc.wait_for(
            message='Ignoring leave_on_load request due to setting.')
