# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import sys
import shlex

import pytest
import pytest_bdd as bdd
from PyQt5.QtNetwork import QSslSocket
bdd.scenarios('downloads.feature')


PROMPT_MSG = ("Asking question <qutebrowser.utils.usertypes.Question "
              "default={!r} mode=PromptMode.download option=None "
              "text=* title='Save file to:'>, *")


@pytest.fixture
def download_dir(tmp_path):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    (downloads / 'subdir').mkdir()
    try:
        os.mkfifo(str(downloads / 'fifo'))
    except AttributeError:
        pass
    unwritable = downloads / 'unwritable'
    unwritable.mkdir()
    unwritable.chmod(0)

    yield downloads

    unwritable.chmod(0o755)


@bdd.given("I set up a temporary download dir")
def temporary_download_dir(quteproc, download_dir):
    quteproc.set_setting('downloads.location.prompt', 'false')
    quteproc.set_setting('downloads.location.remember', 'false')
    quteproc.set_setting('downloads.location.directory', str(download_dir))


@bdd.given("I clean old downloads")
def clean_old_downloads(quteproc):
    quteproc.send_cmd(':download-cancel --all')
    quteproc.send_cmd(':download-clear')


@bdd.when("SSL is supported")
def check_ssl():
    if not QSslSocket.supportsSsl():
        pytest.skip("QtNetwork SSL not supported")


@bdd.when("the unwritable dir is unwritable")
def check_unwritable(tmp_path):
    unwritable = tmp_path / 'downloads' / 'unwritable'
    if os.access(str(unwritable), os.W_OK):
        # Docker container or similar
        pytest.skip("Unwritable dir was writable")


@bdd.when("I wait until the download is finished")
def wait_for_download_finished(quteproc):
    quteproc.wait_for(category='downloads', message='Download * finished')


@bdd.when(bdd.parsers.parse("I wait until the download {name} is finished"))
def wait_for_download_finished_name(quteproc, name):
    quteproc.wait_for(category='downloads',
                      message='Download {} finished'.format(name))


@bdd.when(bdd.parsers.parse('I wait for the download prompt for "{path}"'))
def wait_for_download_prompt(tmp_path, quteproc, path):
    full_path = path.replace('(tmpdir)', str(tmp_path)).replace('/', os.sep)
    quteproc.wait_for(message=PROMPT_MSG.format(full_path))
    quteproc.wait_for(message="Entering mode KeyMode.prompt "
                      "(reason: question asked)")


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should not exist"))
def download_should_not_exist(filename, tmp_path):
    path = tmp_path / 'downloads' / filename
    assert not path.exists()


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should exist"))
def download_should_exist(filename, tmp_path):
    path = tmp_path / 'downloads' / filename
    assert path.exists()


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should be "
                            "{size} bytes big"))
def download_size(filename, size, tmp_path):
    path = tmp_path / 'downloads' / filename
    assert path.stat().st_size == int(size)


@bdd.then(bdd.parsers.parse("The downloaded file {filename} should contain "
                            "{text}"))
def download_contents(filename, text, tmp_path):
    path = tmp_path / 'downloads' / filename
    assert text in path.read_text()


@bdd.then(bdd.parsers.parse('The download prompt should be shown with '
                            '"{path}"'))
def download_prompt(tmp_path, quteproc, path):
    full_path = path.replace('(tmpdir)', str(tmp_path)).replace('/', os.sep)
    quteproc.wait_for(message=PROMPT_MSG.format(full_path))
    quteproc.send_cmd(':mode-leave')


@bdd.when("I set a test python open_dispatcher")
def default_open_dispatcher_python(quteproc, tmp_path):
    cmd = '{} -c "import sys; print(sys.argv[1])"'.format(
        shlex.quote(sys.executable))
    quteproc.set_setting('downloads.open_dispatcher', cmd)


@bdd.when("I open the download")
def download_open(quteproc):
    cmd = '{} -c "import sys; print(sys.argv[1])"'.format(
        shlex.quote(sys.executable))
    quteproc.send_cmd(':download-open {}'.format(cmd))


@bdd.when("I open the download with a placeholder")
def download_open_placeholder(quteproc):
    cmd = '{} -c "import sys; print(sys.argv[1])"'.format(
        shlex.quote(sys.executable))
    quteproc.send_cmd(':download-open {} {{}}'.format(cmd))


@bdd.when("I directly open the download")
def download_open_with_prompt(quteproc):
    cmd = '{} -c pass'.format(shlex.quote(sys.executable))
    quteproc.send_cmd(':prompt-open-download {}'.format(cmd))


@bdd.when(bdd.parsers.parse("I delete the downloaded file {filename}"))
def delete_file(tmp_path, filename):
    (tmp_path / 'downloads' / filename).unlink()


@bdd.then("the FIFO should still be a FIFO")
def fifo_should_be_fifo(tmp_path):
    download_dir = tmp_path / 'downloads'
    assert download_dir.exists()
    assert not (download_dir / 'fifo').is_file()
