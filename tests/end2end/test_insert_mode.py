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

"""Test insert mode settings on html files."""

import logging
import json

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
def test_insert_mode(file_name, elem_id, source, input_text, auto_insert,
                     quteproc, request):
    url_path = 'data/insert_mode_settings/html/{}'.format(file_name)
    quteproc.open_path(url_path)

    quteproc.set_setting('input', 'auto-insert-mode', auto_insert)
    quteproc.send_cmd(':click-element id {}'.format(elem_id))
    quteproc.wait_for(message='Clicked editable element!')
    quteproc.send_cmd(':debug-set-fake-clipboard')

    if source == 'keypress':
        quteproc.press_keys(input_text)
    elif source == 'clipboard':
        if request.config.webengine:
            pytest.xfail(reason="QtWebEngine TODO: caret mode is not "
                         "implemented")
            # Note we actually run the keypress tests with QtWebEngine, as for
            # some reason it selects all the text when clicking the field the
            # second time.
        quteproc.send_cmd(':debug-set-fake-clipboard "{}"'.format(input_text))
        quteproc.send_cmd(':insert-text {clipboard}')

    quteproc.send_cmd(':leave-mode')
    quteproc.send_cmd(':hint all')
    quteproc.wait_for(message='hints: *')
    quteproc.send_cmd(':follow-hint a')
    quteproc.wait_for(message='Clicked editable element!')
    quteproc.send_cmd(':enter-mode caret')
    quteproc.send_cmd(':toggle-selection')
    quteproc.send_cmd(':move-to-prev-word')
    quteproc.send_cmd(':yank selection')

    expected_message = '{} chars yanked to clipboard'.format(len(input_text))
    quteproc.mark_expected(category='message',
                           loglevel=logging.INFO,
                           message=expected_message)
    quteproc.wait_for(
        message='Setting fake clipboard: {}'.format(json.dumps(input_text)))


def test_auto_leave_insert_mode(quteproc):
    url_path = 'data/insert_mode_settings/html/autofocus.html'
    quteproc.open_path(url_path)

    quteproc.set_setting('input', 'auto-leave-insert-mode', 'true')

    quteproc.press_keys('abcd')

    quteproc.send_cmd(':hint all')
    quteproc.wait_for(message='hints: *')

    # Select the disabled input box to leave insert mode
    quteproc.send_cmd(':follow-hint s')
    quteproc.wait_for(message='Clicked non-editable element!')
    quteproc.send_cmd(':enter-mode caret')
    quteproc.send_cmd(':paste-primary')

    expected_message = ('paste-primary: This command is only allowed in '
                        'insert mode, not caret.')
    quteproc.mark_expected(category='message',
                           loglevel=logging.ERROR,
                           message=expected_message)
