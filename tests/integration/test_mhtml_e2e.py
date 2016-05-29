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

"""Test mhtml downloads based on sample files."""

import os
import re
import os.path
import collections

import pytest


def collect_tests():
    basedir = os.path.dirname(__file__)
    datadir = os.path.join(basedir, 'data', 'downloads', 'mhtml')
    files = os.listdir(datadir)
    return files


def normalize_line(line):
    line = line.rstrip('\n')
    line = re.sub('boundary="---=_qute-[0-9a-f-]+"',
                  'boundary="---=_qute-UUID"', line)
    line = re.sub('^-----=_qute-[0-9a-f-]+$', '-----=_qute-UUID', line)
    line = re.sub(r'localhost:\d{1,5}', 'localhost:(port)', line)

    # Depending on Python's mimetypes module/the system's mime files, .js
    # files could be either identified as x-javascript or just javascript
    line = line.replace('Content-Type: application/x-javascript',
                        'Content-Type: application/javascript')

    return line


class DownloadDir:

    """Abstraction over a download directory."""

    def __init__(self, tmpdir):
        self._tmpdir = tmpdir
        self.location = str(tmpdir)

    def read_file(self):
        files = self._tmpdir.listdir()
        assert len(files) == 1

        with open(str(files[0]), 'r', encoding='utf-8') as f:
            return f.readlines()

    def compare_mhtml(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            expected_data = [normalize_line(line) for line in f]
        actual_data = self.read_file()
        actual_data = [normalize_line(line) for line in actual_data]
        assert actual_data == expected_data


@pytest.fixture
def download_dir(tmpdir):
    return DownloadDir(tmpdir)


@pytest.mark.parametrize('test_name', collect_tests())
def test_mhtml(test_name, download_dir, quteproc, httpbin):
    quteproc.set_setting('storage', 'download-directory',
                         download_dir.location)
    quteproc.set_setting('storage', 'prompt-download-directory', 'false')

    test_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            'data', 'downloads', 'mhtml', test_name)
    test_path = 'data/downloads/mhtml/{}'.format(test_name)

    url_path = '{}/{}.html'.format(test_path, test_name)
    quteproc.open_path(url_path)

    download_dest = os.path.join(download_dir.location,
                                 '{}-downloaded.mht'.format(test_name))

    # Wait for favicon.ico to be loaded if there is one
    if os.path.exists(os.path.join(test_dir, 'favicon.png')):
        httpbin.wait_for(path='/{}/favicon.png'.format(test_path))

    # Discard all requests that were necessary to display the page
    httpbin.clear_data()
    quteproc.send_cmd(':download --mhtml --dest "{}"'.format(download_dest))
    quteproc.wait_for(category='downloads', module='mhtml',
                      function='_finish_file',
                      message='File successfully written.')

    expected_file = os.path.join(test_dir, '{}.mht'.format(test_name))
    download_dir.compare_mhtml(expected_file)

    with open(os.path.join(test_dir, 'requests'), encoding='utf-8') as f:
        expected_requests = []
        for line in f:
            if line.startswith('#'):
                continue
            path = '/{}/{}'.format(test_path, line.strip())
            expected_requests.append(httpbin.ExpectedRequest('GET', path))

    actual_requests = httpbin.get_requests()
    # Requests are not hashable, we need to convert to ExpectedRequests
    actual_requests = [httpbin.ExpectedRequest.from_request(req)
                       for req in actual_requests]
    assert (collections.Counter(actual_requests) ==
            collections.Counter(expected_requests))
