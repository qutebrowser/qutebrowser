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

WHITELISTED_HOSTS = ('qutebrowser.org', 'goodhost.gov')

BLOCKED_HOSTS = ('verygoodhost.com',
                 'goodhost.gov',
                 'mediumhost.io',
                 'malware.badhost.org',
                 '4-verybadhost.com',
                 'ads.worsthostever.net',
                 'localhost')

URLS_TO_CHECK = ('http://localhost',
                 'ftp://goodhost.gov',
                 'http://mediumhost.io',
                 'http://malware.badhost.org',
                 'http://4-verybadhost.com',
                 'http://ads.worsthostever.net',
                 'http://verygoodhost.com',
                 'ftp://perfecthost.com',
                 'http://qutebrowser.org')

@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir as datadir"""
    monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                        lambda: str(tmpdir))


# XXX Why does read_hosts needs basedir to be None
# in order to print message 'run adblock-update to read host blocklist' ?
# browser/adblock.py line 138
class BaseDirStub:
    """Mock for objreg.get['args']
       called in adblock.HostBlocker.read_hosts."""
    def __init__(self):
        self.basedir = None

@pytest.yield_fixture
def basedir():
    """Register a Fake basedir."""
    args = BaseDirStub()
    objreg.register('args', args)
    yield args
    objreg.delete('args')


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



def create_zipfile(files, directory, zipname='test'):
    """Returns a zipfile populated with given files and its name."""
    directory = str(directory)
    zipfile_path = os.path.join(directory, zipname + '.zip')
    with zipfile.ZipFile(zipfile_path, 'w') as new_zipfile:
        for file_name in files:
            new_zipfile.write(file_name, arcname=os.path.basename(file_name))
            # Removes path from file name
    return new_zipfile, zipfile_path

def create_blocklist(directory, blocked_hosts=BLOCKED_HOSTS,
                     name='hosts', line_format=None):
    """Returns a QUrl instance linking to a file with given name in given
       directory which contains a list of given blocked_hosts."""
    blocklist = QUrl(os.path.join(str(directory), name))
    with open(blocklist.path(), 'w', encoding='UTF-8') as hosts:
        hosts.write('# Blocked Hosts List #\n\n')
        if line_format == 'etc_hosts':
            for path in blocked_hosts:
                hosts.write('127.0.0.1  ' + path + '\n')
        elif line_format == 'no_hosts':
            hosts.write('This file is not a hosts file')
        else: #one host per line format
            for path in blocked_hosts:
                hosts.write(path + '\n')
    return blocklist

def assert_urls(host_blocker,
                blocked_hosts=BLOCKED_HOSTS,
                whitelisted_hosts=WHITELISTED_HOSTS,
                urls_to_check=URLS_TO_CHECK):
    """Test if urls_to_check are effectively blocked or not by HostBlocker
       Url in blocked_hosts and not in whitelisted_hosts should be blocked
       All other Urls should not be blocked."""
    whitelisted_hosts = list(whitelisted_hosts) + list(host_blocker.WHITELISTED)
    for str_url in urls_to_check:
        url = QUrl(str_url)
        host = url.host()
        if host in blocked_hosts and host not in whitelisted_hosts:
            assert host_blocker.is_blocked(url)
        else:
            assert not host_blocker.is_blocked(url)


class TestHostBlockerUpdate:

    """Tests for function adblock_update of class HostBlocker."""

    def generic_blocklists(self, directory):
        file1 = create_blocklist(directory, BLOCKED_HOSTS[5:], 'hosts', 'etc_hosts')
        file2 = create_blocklist(directory, name='README', line_format='no_hosts')
        file3 = create_blocklist(directory, BLOCKED_HOSTS[:2], 'false_positive')
        files_to_zip = [file1.path(), file2.path(), file3.path()]
        zip_path = create_zipfile(files_to_zip, directory, 'block1')[1]
        remote_blocklist1 = QUrl(zip_path)

        blocklist2 = create_blocklist(directory, [BLOCKED_HOSTS[4]], 'malwarelist', 'etc_hosts')
        zip_path = create_zipfile([blocklist2.path()], directory, 'block2')[1]
        remote_blocklist2 = QUrl(zip_path)

        # A local list with one host per line
        local_blocklist3 = create_blocklist(directory, [BLOCKED_HOSTS[3]], 'mycustomblocklist', 'etc_hosts')
        local_blocklist3.setScheme('file')

        # A list that cannot be read due to its formatting
        remote_blocklist4 = create_blocklist(directory, [BLOCKED_HOSTS[2]], 'badlist', 'no_hosts')

        return [remote_blocklist1, remote_blocklist2, local_blocklist3, remote_blocklist4]

    def test_without_datadir(self, config_stub, tmpdir,
                             monkeypatch, win_registry):
        """No directory for data configured so no hosts file exists.
           CommandError is raised by adblock_update
           Ensure no url is blocked."""
        config_stub.data = {'content':
                            {'host-block-lists': self.generic_blocklists(tmpdir),
                             'host-blocking-enabled': True}}
        monkeypatch.setattr('qutebrowser.utils.standarddir.data',
                            lambda: None)
        host_blocker = adblock.HostBlocker()
        with pytest.raises(cmdexc.CommandError):
            host_blocker.adblock_update(0)
        host_blocker.read_hosts()
        for str_url in URLS_TO_CHECK:
            assert not host_blocker.is_blocked(QUrl(str_url))

    def test_disabled_blocking(self, basedir, config_stub, download_stub,
                               data_tmpdir, tmpdir, win_registry):
        """Ensure that no url is blocked when host blocking is disabled."""
        config_stub.data = {'content':
                            {'host-block-lists': self.generic_blocklists(tmpdir),
                             'host-blocking-enabled': False}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()
        for str_url in URLS_TO_CHECK:
            assert not host_blocker.is_blocked(QUrl(str_url))

    def test_no_blocklist(self, config_stub, download_stub,
                          data_tmpdir, basedir, tmpdir, win_registry):
        """Ensure no host is blocked when no blocklist exists."""
        config_stub.data = {'content':
                            {'host-block-lists' : None,
                             'host-blocking-enabled': True}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        host_blocker.read_hosts()
        for str_url in URLS_TO_CHECK:
            assert not host_blocker.is_blocked(QUrl(str_url))

    def test_successful_update(self, config_stub, basedir, download_stub,
                               data_tmpdir, tmpdir, win_registry):
        config_stub.data = {'content':
                            {'host-block-lists': self.generic_blocklists(tmpdir),
                             'host-blocking-enabled': True,
                             'host-blocking-whitelist': None}}
        host_blocker = adblock.HostBlocker()
        host_blocker.adblock_update(0)
        # Simulate download is finished
        # XXX Is it ok to use private attribute hostblocker._in_progress ?
        while host_blocker._in_progress != []:
            host_blocker._in_progress[0].finished.emit()
        host_blocker.read_hosts()
        assert_urls(host_blocker, BLOCKED_HOSTS[3:], whitelisted_hosts=[])

    # def test_remote_text(self, config_stub, basedir, download_stub,
    #                      data_tmpdir, tmpdir, win_registry):
    #     """Update with single fakely remote text blocklist.
    #        Ensure urls from hosts in this blocklist get blocked."""
    #     blocklist = create_blocklist(tmpdir)
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [blocklist],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     # Simulate download is finished
    #     # XXX Is it ok to use private attribute hostblocker._in_progress ?
    #     host_blocker._in_progress[0].finished.emit()
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

    # def test_remote_zip_single(self, config_stub, basedir, download_stub,
    #                            data_tmpdir, tmpdir, win_registry):
    #     """Update with single fakely remote zip containing one blocklist file.
    #        Ensure urls from hosts in this blocklist get blocked."""
    #     blocklist = create_blocklist(tmpdir)
    #     zip_url = QUrl(create_zipfile([blocklist.path()], tmpdir)[1])
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [zip_url],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     host_blocker._in_progress[0].finished.emit()
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

    # # FIXME adblock.guess_zip_filename should raise FileNotFound Error
    # # as no files in the zip are called hosts
    # def test_remote_zip_multi1(self, config_stub, basedir, download_stub,
    #                            data_tmpdir, tmpdir, win_registry):
    #     """Update with single fakely remote zip containing two files.
    #        None of them is called hosts, FileNotFoundError should be raised."""
    #     file1 = create_blocklist(tmpdir, name='file1.txt')
    #     file2_hosts = ['testa.com', 'testb.com']
    #     file2 = create_blocklist(tmpdir, file2_hosts, name='file2.txt')
    #     files_to_zip = [file1.path(), file2.path()]
    #     zip_path = create_zipfile(files_to_zip, tmpdir)[1]
    #     zip_url = QUrl(zip_path)
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [zip_url],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     #with pytest.raises(FileNotFoundError):
    #     host_blocker.adblock_update(0)
    #     host_blocker._in_progress[0].finished.emit()
    #     host_blocker.read_hosts()
    #     for str_url in URLS_TO_CHECK:
    #         assert not host_blocker.is_blocked(QUrl(str_url))

    # def test_remote_zip_multi2(self, config_stub, basedir, download_stub,
    #                            data_tmpdir, tmpdir, win_registry):
    #     """Update with single fakely remote zip containing two files.
    #        One of them is called hosts and should be used as blocklist.
    #        Ensure urls from hosts in this blocklist get blocked
    #        and the hosts from the other file are not."""
    #     file1 = create_blocklist(tmpdir, name='hosts.txt')
    #     file2_hosts = ['testa.com', 'testb.com']
    #     file2 = create_blocklist(tmpdir, file2_hosts, name='file2.txt')
    #     files_to_zip = [file1.path(), file2.path()]
    #     zip_path = create_zipfile(files_to_zip, tmpdir)[1]
    #     zip_url = QUrl(zip_path)
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [zip_url],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     host_blocker._in_progress[0].finished.emit()
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

    # def test_local_text(self, config_stub, basedir, download_stub,
    #                     data_tmpdir, tmpdir, win_registry):
    #     """Update with single local text blocklist.
    #        Ensure urls from hosts in this blocklist get blocked."""
    #     blocklist = create_blocklist(tmpdir)
    #     blocklist.setScheme("file")
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [blocklist],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

    # def test_local_zip_single(self, config_stub, basedir, download_stub,
    #                            data_tmpdir, tmpdir, win_registry):
    #     """Update with single local zip containing one file.
    #        Ensure urls from hosts in this blocklist get blocked."""
    #     blocklist = create_blocklist(tmpdir)
    #     zip_url = QUrl(create_zipfile([blocklist.path()], tmpdir)[1])
    #     zip_url.setScheme('file')
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [zip_url],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

    # def test_local_zip_multi(self, config_stub, basedir, download_stub,
    #                          data_tmpdir, tmpdir, win_registry):
    #     """Update with single local zip containing two files.
    #        One of them is called hosts and should be used as blocklist.
    #        Ensure urls from hosts in this blocklist get blocked
    #        and the hosts from the other file are not."""
    #     file1 = create_blocklist(tmpdir, name='hosts.txt')
    #     file2_hosts = ['testa.com', 'testb.com']
    #     file2 = create_blocklist(tmpdir, file2_hosts, name='file2.txt')
    #     files_to_zip = [file1.path(), file2.path()]
    #     zip_path = create_zipfile(files_to_zip, tmpdir)[1]
    #     zip_url = QUrl(zip_path)
    #     zip_url.setScheme('file')
    #     config_stub.data = {'content':
    #                         {'host-block-lists': [zip_url],
    #                          'host-blocking-enabled': True,
    #                          'host-blocking-whitelist': None}}
    #     host_blocker = adblock.HostBlocker()
    #     host_blocker.adblock_update(0)
    #     host_blocker.read_hosts()
    #     assert_urls(host_blocker, whitelisted_hosts=[])

class TestHostBlockerIsBlocked:

    """Tests for function adblock_update of class HostBlocker."""

    def test_with_whitelist(self, config_stub, basedir, download_stub,
                            data_tmpdir, tmpdir, win_registry):
        """"""
        # Simulate adblock_update has already been run,
        # exclude localhost from blocked-hosts file
        filtered_blocked_hosts = BLOCKED_HOSTS[:-1]
        blocklist = create_blocklist(tmpdir,
                                     blocked_hosts=filtered_blocked_hosts,
                                     name="blocked-hosts")
        config_stub.data = {'content':
                            {'host-block-lists': [blocklist],
                             'host-blocking-enabled': True,
                             'host-blocking-whitelist': WHITELISTED_HOSTS}}
        host_blocker = adblock.HostBlocker()
        host_blocker.read_hosts()
        assert_urls(host_blocker)
