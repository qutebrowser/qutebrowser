# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


@pytest.mark.parametrize(['file_name', 'elem_id', 'source', 'input_text',
                          'auto_insert'], [
    ('textarea.html', 'qute-textarea', 'clipboard', 'qutebrowser', 'false'),
    ('textarea.html', 'qute-textarea', 'keypress', 'superqutebrowser',
     'false'),
    ('input.html', 'qute-input', 'clipboard', 'amazingqutebrowser', 'false'),
    ('input.html', 'qute-input', 'keypress', 'awesomequtebrowser', 'false'),
    ('autofocus.html', 'qute-input-autofocus', 'keypress', 'cutebrowser',
     'true'),
])
@pytest.mark.parametrize('zoom', [100, 125, 250])
def test_insert_mode(file_name, elem_id, source, input_text, auto_insert, zoom,
                     quteproc, request):
    url_path = 'data/insert_mode_settings/html/{}'.format(file_name)
    quteproc.open_path(url_path)

    quteproc.set_setting('input.insert_mode.auto_focused', auto_insert)
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
