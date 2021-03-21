# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import logging

import pytest_bdd as bdd
bdd.scenarios('prompts.feature')


@bdd.when("I load an SSL page")
def load_ssl_page(quteproc, ssl_server):
    # We don't wait here as we can get an SSL question.
    quteproc.open_path('/', port=ssl_server.port, https=True, wait=False,
                       new_tab=True)


@bdd.when("I wait until the SSL page finished loading")
def wait_ssl_page_finished_loading(quteproc, ssl_server):
    quteproc.wait_for_load_finished('/', port=ssl_server.port, https=True,
                                    load_status='warn')


@bdd.when("I load an SSL resource page")
def load_ssl_resource_page(quteproc, server, ssl_server):
    # We don't wait here as we can get an SSL question.
    quteproc.open_path(f'https-script/{ssl_server.port}', port=server.port, wait=False)


@bdd.when("I wait until the SSL resource page finished loading")
def wait_ssl_resource_page_finished_loading(quteproc, server, ssl_server):
    quteproc.wait_for_load_finished(f'https-script/{ssl_server.port}', port=server.port)


@bdd.when("I wait for a prompt")
def wait_for_prompt(quteproc):
    quteproc.wait_for(message='Asking question *')


@bdd.then("no prompt should be shown")
def no_prompt_shown(quteproc):
    quteproc.ensure_not_logged(message='Entering mode KeyMode.* (reason: '
                                       'question asked)')


@bdd.then("a SSL error page should be shown")
def ssl_error_page(request, quteproc):
    if request.config.webengine:
        quteproc.wait_for(message="Certificate error: *")

        msg = quteproc.wait_for(message="Load error: *")
        msg.expected = True

        assert msg.message == 'Load error: ERR_CERT_AUTHORITY_INVALID'
    else:
        line = quteproc.wait_for(message='Error while loading *: SSL handshake failed')
        line.expected = True
        quteproc.wait_for(message="Changing title for idx * to 'Error loading page: *'")
        content = quteproc.get_content().strip()
        assert "Unable to load page" in content


def test_certificate_error_load_status(request, quteproc, ssl_server):
    """If we load the same page twice, we should get a 'warn' status twice."""
    quteproc.set_setting('content.tls.certificate_errors', 'load-insecurely')

    for i in range(2):
        quteproc.open_path('/', port=ssl_server.port, https=True, wait=False,
                           new_tab=True)
        if i == 0 or not request.config.webengine:
            # Error is only logged on the first error with QtWebEngine
            quteproc.mark_expected(category='message',
                                   loglevel=logging.ERROR,
                                   message="Certificate error: *")
        quteproc.wait_for_load_finished('/', port=ssl_server.port, https=True,
                                        load_status='warn')
