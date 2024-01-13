# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test mhtml downloads based on sample files."""

import pathlib
import re
import collections

import pytest


def collect_tests():
    basedir = pathlib.Path(__file__).parent
    datadir = basedir / 'data' / 'downloads' / 'mhtml'
    files = [x.name for x in datadir.iterdir()]
    return files


def normalize_line(line):
    line = line.rstrip('\n')
    line = re.sub('boundary="---=_qute-[0-9a-f-]+"',
                  'boundary="---=_qute-UUID"', line)
    line = re.sub('^-----+=_qute-[0-9a-f-]+$',
                  '-----=_qute-UUID', line)
    line = re.sub(r'localhost:\d{1,5}', 'localhost:(port)', line)

    # Depending on Python's mimetypes module/the system's mime files, .js
    # files could be either identified as x-javascript or just javascript
    line = line.replace('Content-Type: application/x-javascript',
                        'Content-Type: application/javascript')

    # With QtWebKit and newer Werkzeug versions, we also get an encoding
    # specified.
    line = line.replace('javascript; charset=utf-8', 'javascript')

    return line


class DownloadDir:

    """Abstraction over a download directory."""

    def __init__(self, tmp_path, config):
        self._tmp_path = tmp_path
        self._config = config
        self.location = str(tmp_path)

    def read_file(self):
        files = list(self._tmp_path.iterdir())
        assert len(files) == 1
        return files[0].read_text(encoding='utf-8').splitlines()

    def sanity_check_mhtml(self):
        assert 'Content-Type: multipart/related' in '\n'.join(self.read_file())

    def compare_mhtml(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            expected_data = '\n'.join(normalize_line(line)
                                      for line in f
                                      if normalize_line(line) is not None)
        actual_data = '\n'.join(normalize_line(line)
                                for line in self.read_file())
        assert actual_data == expected_data


@pytest.fixture
def download_dir(tmp_path, pytestconfig):
    return DownloadDir(tmp_path, pytestconfig)


def _test_mhtml_requests(test_dir, test_path, server):
    with (test_dir / 'requests').open(encoding='utf-8') as f:
        expected_requests = []
        for line in f:
            if line.startswith('#'):
                continue
            path = '/{}/{}'.format(test_path, line.strip())
            expected_requests.append(server.ExpectedRequest('GET', path))

    actual_requests = server.get_requests()
    # Requests are not hashable, we need to convert to ExpectedRequests
    actual_requests = [server.ExpectedRequest.from_request(req)
                       for req in actual_requests]
    assert (collections.Counter(actual_requests) ==
            collections.Counter(expected_requests))


@pytest.mark.parametrize('test_name', collect_tests())
def test_mhtml(request, test_name, download_dir, quteproc, server):
    quteproc.set_setting('downloads.location.directory', download_dir.location)
    quteproc.set_setting('downloads.location.prompt', 'false')

    test_dir = (pathlib.Path(__file__).parent.resolve()
                / 'data' / 'downloads' / 'mhtml' / test_name)
    test_path = 'data/downloads/mhtml/{}'.format(test_name)

    url_path = '{}/{}.html'.format(test_path, test_name)
    quteproc.open_path(url_path)

    download_dest = (pathlib.Path(download_dir.location)
                     / '{}-downloaded.mht'.format(test_name))

    # Wait for favicon.ico to be loaded if there is one
    if (test_dir / 'favicon.png').exists():
        server.wait_for(path='/{}/favicon.png'.format(test_path))

    # Discard all requests that were necessary to display the page
    server.clear_data()
    quteproc.send_cmd(':download --mhtml --dest "{}"'.format(download_dest))
    quteproc.wait_for(category='downloads',
                      message='File successfully written.')

    if request.config.webengine:
        download_dir.sanity_check_mhtml()
        return

    filename = test_name + '.mht'
    expected_file = test_dir / filename

    download_dir.compare_mhtml(expected_file)
    _test_mhtml_requests(test_dir, test_path, server)
