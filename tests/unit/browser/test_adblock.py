# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
#!/usr/bin/env python3

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.browser.adblock."""

import os
import zipfile
import shutil

import pytest

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

from qutebrowser.browser import adblock
from qutebrowser.config import configexc
from qutebrowser.utils import objreg

UNDESIRED_HOSTS = ['badsite.org','verybadsite.com','worstsiteever.net']

class FakeDownloadItem(QObject):
    """Mock browser.downloads.DownloadItem."""

    finished = pyqtSignal()

    def __init__(self, fileobj):
        super().__init__()
        self.fileobj = fileobj
        self.successful = True


class FakeDownloadManager:
    """Mock browser.downloads.DownloadManager."""

    def get(self, url, fileobj, **kwargs):
        """Returns a FakeDownloadItem instance with a fileobj
           copied from given fake url file."""
        download_item = FakeDownloadItem(fileobj)
        with open(url.path(), 'rb') as fake_url_file :
            # Ensure cursors are at position 0 before copying
            fake_url_file.seek(0)
            download_item.fileobj.seek(0)
            shutil.copyfileobj(fake_url_file, download_item.fileobj)
        return download_item

@pytest.yield_fixture
def download_stub(win_registry):
    """Register a FakeDownloadManager."""
    stub = FakeDownloadManager()
    objreg.register('download-manager', stub,
                    scope='window', window='last-focused')
    yield stub
    objreg.delete('download-manager', scope='window', window='last-focused')

@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Use tmpdir as datadir"""
    monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                        lambda: str(tmpdir))

def create_text_files(files_names, directory):
    """Returns a list of text files created
    with given names in given directory."""
    directory = str(directory)
    created_files = []
    for file_name in files_names:
        test_file = os.path.join(directory, file_name)
        with open(test_file, 'w', encoding='utf-8') as current_file:
            current_file.write('www.' + file_name + '.com')
        created_files.append(test_file)
    return created_files

def create_zipfile(files_names, directory):
    """Returns a zipfile populated with created files and its name."""
    directory = str(directory)
    files = create_text_files(files_names, directory)
    # include created files in a ZipFile
    zipfile_name = os.path.join(directory, 'test.zip')
    with zipfile.ZipFile(zipfile_name, 'w') as new_zipfile:
        for file_name in files:
            new_zipfile.write(file_name, arcname=os.path.basename(file_name))
            # Removes path from file name
    return new_zipfile, zipfile_name


class TestGuessZipFilename:
    """Test function adblock.guess_zip_filename()."""

    def test_with_single_file(self, tmpdir):
        """Zip provided only contains a single file."""
        zf = create_zipfile(['test_a'], tmpdir)[0]
        assert adblock.guess_zip_filename(zf) == 'test_a'

    def test_with_multiple_files(self, tmpdir):
        """Zip provided contains multiple files including hosts."""
        names = ['test_a', 'test_b', 'hosts', 'test_c']
        zf = create_zipfile(names, tmpdir)[0]
        assert adblock.guess_zip_filename(zf) == 'hosts'

    def test_without_hosts_file(self, tmpdir):
        """Zip provided does not contain any hosts file."""
        names = ['test_a', 'test_b', 'test_d', 'test_c']
        zf = create_zipfile(names, tmpdir)[0]
        with pytest.raises(FileNotFoundError):
            adblock.guess_zip_filename(zf)


class TestGetFileObj:
    """Test Function adblock.get_fileobj()."""

    def test_with_zipfile(self, tmpdir):
        """File provided is a zipfile."""
        names = ['test_a', 'test_b', 'hosts', 'test_c']
        zf_name = create_zipfile(names, tmpdir)[1]
        zipobj = open(zf_name, 'rb')
        assert adblock.get_fileobj(zipobj).read() == "www.hosts.com"

    def test_with_text_file(self, tmpdir):
        """File provided is not a zipfile."""
        test_file = open(create_text_files(['testfile'], tmpdir)[0], 'rb')
        assert adblock.get_fileobj(test_file).read() == "www.testfile.com"


class TestIsWhitelistedHost:
    """Test function adblock.is_whitelisted_host."""

    def test_without_hosts(self, config_stub):
        """No hosts are whitelisted."""
        config_stub.data = {'content': {'host-blocking-whitelist': None}}
        assert not adblock.is_whitelisted_host('qutebrowser.org')

    def test_with_match(self, config_stub):
        """Given host is in the whitelist."""
        config_stub.data = {'content':
                            {'host-blocking-whitelist': ['qutebrowser.org']}}
        assert adblock.is_whitelisted_host('qutebrowser.org')

    def test_without_match(self, config_stub):
        """Given host is not in the whitelist."""
        config_stub.data = {'content':
                            {'host-blocking-whitelist':['qutebrowser.org']}}
        assert not adblock.is_whitelisted_host('cutebrowser.org')


class TestHostBlocker:
    """Tests for class HostBlocker."""

    def test_without_datadir(self, config_stub, monkeypatch):
        """No directory for data configured, no hosts file present."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                            lambda: None)
        host_blocker = adblock.HostBlocker()
        assert host_blocker._hosts_file == None

    def test_with_datadir(self, config_stub, data_tmpdir, tmpdir):
        #TODO Remove since now useless as already tested by test_update
        host_blocker = adblock.HostBlocker()
        hosts_file_path = os.path.join(str(tmpdir), 'blocked-hosts')
        assert host_blocker._hosts_file == hosts_file_path

    def test_update_with_fake_url(self, config_stub, download_stub,
                                  data_tmpdir, tmpdir, win_registry):
        """Test update, checked Url host is in the new blocklist added by update
           Remote Url is faked by a local file."""
        # Create blocklist and add it to config
        blocklist = QUrl(os.path.join(str(tmpdir), 'new_hosts.txt'))
        with open(blocklist.path(), 'w', encoding='UTF-8') as hosts:
            for path in UNDESIRED_HOSTS:
                hosts.write(path + '\n')
        config_stub.data = {'content':
                            {'host-block-lists': [blocklist],
                             'host-blocking-enabled': True,
                             'host-blocking-whitelist': None}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        #Simulate download is finished
        host_blocker._in_progress[0].finished.emit()
        url_to_check = QUrl("www.ugly.verybadsite.com")
        url_to_check.setHost("verybadsite.com")
        assert host_blocker.is_blocked(url_to_check)

    def test_update_with_local_file(self, config_stub, download_stub,
                                    data_tmpdir, tmpdir, win_registry):
        """Test update, checked Url host is in the new blocklist added by update
           Url is a local file."""
        # Create blocklist and add it to config
        local_blocklist = QUrl(os.path.join(str(tmpdir), 'new_hosts.txt'))
        local_blocklist.setScheme("file")
        with open(local_blocklist.path(), 'w', encoding='UTF-8') as hosts:
            for path in UNDESIRED_HOSTS:
                hosts.write(path + '\n')
        config_stub.data = {'content':
                            {'host-block-lists': [local_blocklist],
                             'host-blocking-enabled': True,
                             'host-blocking-whitelist': None}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        url_to_check = QUrl("www.ugly.verybadsite.com")
        url_to_check.setHost("verybadsite.com")
        assert host_blocker.is_blocked(url_to_check)
