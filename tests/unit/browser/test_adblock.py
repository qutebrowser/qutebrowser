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
from qutebrowser.utils import objreg
from qutebrowser.commands import cmdexc


WHITELISTED_HOSTS = ['qutebrowser.org', 'badsite.org']
BLOCKED_HOSTS = ['badsite.org', 'localhost',
                 'verybadsite.com', 'worstsiteever.net']
URLS_TO_CHECK = ['http://verybadsite.com', 'http://badsite.org',
                 'http://localhost', 'http://qutebrowser.org',
                 'http://a.com', 'http://b.com']

class BaseDirStub:
    """Mock for objreg.get['args'] called in adblock.HostBlocker.read_hosts."""
    def __init__(self):
        self.basedir = None


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
        with open(url.path(), 'rb') as fake_url_file:
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

@pytest.yield_fixture
def basedir():
    """Register a Fake basedir."""
    args = BaseDirStub()
    objreg.register('args', args)
    yield args
    objreg.delete('args')

@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Use tmpdir as datadir"""
    monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                        lambda: str(tmpdir))

def create_zipfile(files, directory):
    """Returns a zipfile populated with given files and its name."""
    directory = str(directory)
    zipfile_path = os.path.join(directory, 'test.zip')
    with zipfile.ZipFile(zipfile_path, 'w') as new_zipfile:
        for file_name in files:
            new_zipfile.write(file_name, arcname=os.path.basename(file_name))
            # Removes path from file name
    return new_zipfile, zipfile_path

def create_blocklist(blocked_hosts, name, directory):
    """Returns a QUrl instance linking to a file with given name in given
       directory which contains a list of given blocked_hosts."""
    blocklist = QUrl(os.path.join(str(directory), name))
    with open(blocklist.path(), 'w', encoding='UTF-8') as hosts:
        for path in blocked_hosts:
            hosts.write(path + '\n')
    return blocklist

def assert_urls(host_blocker, blocked_hosts, whitelisted_hosts, urls_to_check):
    """Test if urls_to_check are effectively blocked or not by HostBlocker."""
    for str_url in urls_to_check:
        url = QUrl(str_url)
        host = url.host()
        if host in blocked_hosts and host not in whitelisted_hosts:
            assert host_blocker.is_blocked(url)
        else:
            assert not host_blocker.is_blocked(url)


class TestHostBlocker:
    """Tests for class HostBlocker."""

    def test_unsuccessful_update(self, config_stub, monkeypatch, win_registry):
        """No directory for data configured so no hosts file exists."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                            lambda: None)
        host_blocker = adblock.HostBlocker()
        with pytest.raises(cmdexc.CommandError):
            host_blocker.adblock_update(0)
        assert host_blocker.read_hosts() is None

    def test_host_blocking_disabled(self, basedir, config_stub, download_stub,
                                    data_tmpdir, tmpdir, win_registry):
        """Assert that no host is blocked when blocking is disabled."""
        blocklist = create_blocklist(BLOCKED_HOSTS, 'hosts.txt', tmpdir)
        config_stub.data = {'content':
                            {'host-block-lists': [blocklist],
                             'host-blocking-enabled': False}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        host_blocker.read_hosts()
        for strurl in URLS_TO_CHECK:
            url = QUrl(strurl)
            assert not host_blocker.is_blocked(url)

    def test_update_no_blocklist(self, config_stub, download_stub,
                                 data_tmpdir, basedir, win_registry):
        """Assert that no host is blocked when no blocklist exists."""
        config_stub.data = {'content':
                            {'host-block-lists' : None,
                             'host-blocking-enabled': True}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        host_blocker.read_hosts()
        for strurl in URLS_TO_CHECK:
            url = QUrl(strurl)
            assert not host_blocker.is_blocked(url)

    def test_successful_update(self, config_stub, basedir, download_stub,
                               data_tmpdir, tmpdir, win_registry):
        """
           Test successfull update with :
           - fake remote text file
           - local text file
           - fake remote zip file (contains 1 text file)
           - fake remote zip file (contains 2 text files, 0 named hosts)
           - fake remote zip file (contains 2 text files, 1 named hosts).
        """

        # Primary test with fake remote text file
        blocklist = create_blocklist(BLOCKED_HOSTS, 'blocklist.txt', tmpdir)
        config_stub.data = {'content':
                            {'host-block-lists': [blocklist],
                             'host-blocking-enabled': True,
                             'host-blocking-whitelist': WHITELISTED_HOSTS}}
        host_blocker = adblock.HostBlocker()
        whitelisted = list(host_blocker.WHITELISTED) + WHITELISTED_HOSTS
        # host file has not been created yet, message run-adblock will be sent
        # host_blocker.read_hosts()
        host_blocker.adblock_update(0)
        #Simulate download is finished
        host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()
        assert_urls(host_blocker, BLOCKED_HOSTS, whitelisted, URLS_TO_CHECK)

        # Alternative test with local file
        local_blocklist = blocklist
        local_blocklist.setScheme("file")
        config_stub.set('content', 'host-block-lists', [local_blocklist])
        host_blocker.adblock_update(0)
        host_blocker.read_hosts()
        assert_urls(host_blocker, BLOCKED_HOSTS, whitelisted, URLS_TO_CHECK)

        # Alternative test with fake remote zip file containing one file
        zip_blocklist_url = QUrl(create_zipfile([blocklist.path()], tmpdir)[1])
        config_stub.set('content', 'host-block-lists', [zip_blocklist_url])
        host_blocker.adblock_update(0)
        #Simulate download is finished
        host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()
        assert_urls(host_blocker, BLOCKED_HOSTS, whitelisted, URLS_TO_CHECK)

        # Alternative test with fake remote zip file containing multiple files
        # FIXME adblock.guess_zip_filename should raise FileNotFound Error
        # as no files in the zip are called hosts
        first_file = create_blocklist(BLOCKED_HOSTS, 'file1.txt', tmpdir)
        second_file = create_blocklist(['a.com', 'b.com'], 'file2.txt', tmpdir)
        files_to_zip = [first_file.path(), second_file.path()]
        zip_blocklist_path = create_zipfile(files_to_zip, tmpdir)[1]
        zip_blocklist_url = QUrl(zip_blocklist_path)
        config_stub.set('content', 'host-block-lists', [zip_blocklist_url])
        host_blocker.adblock_update(0)
        #Simulate download is finished
        with pytest.raises(FileNotFoundError):
            host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()

        # Alternative test with fake remote zip file containing multiple files
        # Including a file called hosts
        first_file = create_blocklist(BLOCKED_HOSTS, 'hosts.txt', tmpdir)
        second_file = create_blocklist(['a.com', 'b.com'], 'file2.txt', tmpdir)
        files_to_zip = [first_file.path(), second_file.path()]
        zip_blocklist_path = create_zipfile(files_to_zip, tmpdir)[1]
        zip_blocklist_url = QUrl(zip_blocklist_path)
        config_stub.set('content', 'host-block-lists', [zip_blocklist_url])
        host_blocker.adblock_update(0)
        #Simulate download is finished
        host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()
        assert_urls(host_blocker, BLOCKED_HOSTS, whitelisted, URLS_TO_CHECK)
