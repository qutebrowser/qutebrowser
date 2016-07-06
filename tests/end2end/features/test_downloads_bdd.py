# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os

import pytest_bdd as bdd
bdd.scenarios('downloads.feature')


@bdd.given("I set up a temporary download dir")
def temporary_download_dir(quteproc, tmpdir):
    quteproc.set_setting('storage', 'prompt-download-directory', 'false')
    quteproc.set_setting('storage', 'remember-download-directory', 'false')
    quteproc.set_setting('storage', 'download-directory', str(tmpdir))


@bdd.given("I clean old downloads")
def clean_old_downloads(quteproc):
    quteproc.send_cmd(':download-cancel --all')
    quteproc.send_cmd(':download-clear')


@bdd.when("I wait until the download is finished")
def wait_for_download_finished(quteproc):
    quteproc.wait_for(category='downloads', message='Download finished')


@bdd.when("I download an SSL page")
def download_ssl_page(quteproc, ssl_server):
    quteproc.send_cmd(':download https://localhost:{}/'
                      .format(ssl_server.port))


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should not exist"))
def download_should_not_exist(filename, tmpdir):
    path = tmpdir / filename
    assert not path.check()


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should exist"))
def download_should_exist(filename, tmpdir):
    path = tmpdir / filename
    assert path.check()


@bdd.then(bdd.parsers.parse('The download prompt should be shown with '
                            '"{path}"'))
def download_prompt(tmpdir, quteproc, path):
    full_path = path.replace('{downloaddir}', str(tmpdir)).replace('/', os.sep)
    msg = ("Asking question <qutebrowser.utils.usertypes.Question "
           "default={full_path!r} mode=<PromptMode.download: 5> "
           "text='Save file to:'>, *".format(full_path=full_path))
    quteproc.wait_for(message=msg)
    quteproc.send_cmd(':leave-mode')
