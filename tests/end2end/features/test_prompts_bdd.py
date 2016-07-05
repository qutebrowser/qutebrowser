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

import pytest_bdd as bdd
bdd.scenarios('prompts.feature')


@bdd.when("I load an SSL page")
def load_ssl_page(quteproc, ssl_server):
    # We don't wait here as we can get an SSL question.
    quteproc.open_path('/', port=ssl_server.port, https=True, wait=False)


@bdd.when("I wait until the SSL page finished loading")
def wait_ssl_page_finished_loading(quteproc, ssl_server):
    quteproc.wait_for_load_finished('/', port=ssl_server.port, https=True,
                                    load_status='warn')


@bdd.when("I click the button")
def click_button(quteproc):
    quteproc.send_cmd(':hint')
    quteproc.send_cmd(':follow-hint a')


@bdd.when("I wait for a prompt")
def wait_for_prompt(quteproc):
    quteproc.wait_for(message='Entering mode KeyMode.* (reason: question '
                              'asked)')


@bdd.then("no prompt should be shown")
def no_prompt_shown(quteproc):
    quteproc.ensure_not_logged(message='Entering mode KeyMode.* (reason: '
                                       'question asked)')
