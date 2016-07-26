# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
#!/usr/bin/env python3

# Copyright 2015 Corentin Julé <corentinjule@gmail.com>
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
import zipfile
import shutil

import pytest

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

from qutebrowser.browser import adblock
from qutebrowser.utils import objreg
from qutebrowser.commands import cmdexc

pytestmark = pytest.mark.usefixtures('qapp', 'config_tmpdir')

# TODO See ../utils/test_standarddirutils for OSError and caplog assertion

WHITELISTED_HOSTS = ('qutebrowser.org', 'mediumhost.io')

BLOCKLIST_HOSTS = ('localhost',
                   'mediumhost.io',
                   'malware.badhost.org',
                   '4-verybadhost.com',
                   'ads.worsthostever.net')

CLEAN_HOSTS = ('goodhost.gov', 'verygoodhost.com')

URLS_TO_CHECK = ('http://localhost',
                 'http://mediumhost.io',
                 'ftp://malware.badhost.org',
                 'http://4-verybadhost.com',
                 'http://ads.worsthostever.net',
                 'http://goodhost.gov',
                 'ftp://verygoodhost.com',
                 'http://qutebrowser.org')


class BaseDirStub:

    """Mock for objreg.get('args') called in adblock.HostBlocker.read_hosts."""

    def __init__(self):
        self.basedir = None


@pytest.fixture
def basedir(fake_args):
    """Register a Fake basedir."""
    fake_args.basedir = None


class FakeDownloadItem(QObject):

    """Mock browser.downloads.DownloadItem."""

    finished = pyqtSignal()

    def __init__(self, fileobj, name, parent=None):
        super().__init__(parent)
        self.fileobj = fileobj
        self.name = name
        self.successful = True


class FakeDownloadManager:

    """Mock browser.downloads.DownloadManager."""

    def get(self, url, target, **kwargs):
        """Return a FakeDownloadItem instance with a fileobj.

        The content is copied from the file the given url links to.
        """
        download_item = FakeDownloadItem(target.fileobj, name=url.path())
        with open(url.path(), 'rb') as fake_url_file:
            shutil.copyfileobj(fake_url_file, download_item.fileobj)
        return download_item


@pytest.yield_fixture
def download_stub(win_registry):
    """Register a FakeDownloadManager."""
    stub = FakeDownloadManager()
    objreg.register('download-manager', stub,
                    scope='window', window='last-focused')
    yield
    objreg.delete('download-manager', scope='window', window='last-focused')


def create_zipfile(directory, files, zipname='test'):
    """Return a path to a newly created zip file.

    Args:
        directory: path object where to create the zip file
        files: list of paths to each file to add in the zipfile
        zipname: name to give to the zip file.
    """
    zipfile_path = directory / zipname + '.zip'
    with zipfile.ZipFile(str(zipfile_path), 'w') as new_zipfile:
        for file_path in files:
            new_zipfile.write(str(file_path),
                              arcname=os.path.basename(str(file_path)))
            # Removes path from file name
    return str(zipfile_path)


def create_blocklist(directory, blocked_hosts=BLOCKLIST_HOSTS,
                     name='hosts', line_format='one_per_line'):
    """Return a path to a blocklist file.

    Args:
        directory: path object where to create the blocklist file
        blocked_hosts: an iterable of string hosts to add to the blocklist
        name: name to give to the blocklist file
        line_format: 'etc_hosts'  -->  /etc/hosts format
                    'one_per_line'  -->  one host per line format
                    'not_correct'  -->  Not a correct hosts file format.
    """
    blocklist_file = directory / name
    with open(str(blocklist_file), 'w', encoding='UTF-8') as blocklist:
        # ensure comments are ignored when processing blocklist
        blocklist.write('# Blocked Hosts List #\n\n')
        if line_format == 'etc_hosts':  # /etc/hosts like format
            for host in blocked_hosts:
                blocklist.write('127.0.0.1  ' + host + '\n')
        elif line_format == 'one_per_line':
            for host in blocked_hosts:
                blocklist.write(host + '\n')
        elif line_format == 'not_correct':
            for host in blocked_hosts:
                blocklist.write(host + ' This is not a correct hosts file\n')
        else:
            raise ValueError('Incorrect line_format argument')
    return str(blocklist_file)


def assert_urls(host_blocker, blocked=BLOCKLIST_HOSTS,
                whitelisted=WHITELISTED_HOSTS, urls_to_check=URLS_TO_CHECK):
    """Test if Urls to check are blocked or not by HostBlocker.

    Ensure URLs in 'blocked' and not in 'whitelisted' are blocked.
    All other URLs must not be blocked.
    """
    whitelisted = list(whitelisted) + list(host_blocker.WHITELISTED)
    for str_url in urls_to_check:
        url = QUrl(str_url)
        host = url.host()
        if host in blocked and host not in whitelisted:
            assert host_blocker.is_blocked(url)
        else:
            assert not host_blocker.is_blocked(url)


def generic_blocklists(directory):
    """Return a generic list of files to be used in hosts-block-lists option.

    This list contains :
    - a remote zip file with 1 hosts file and 2 useless files
    - a remote zip file with only useless files
        (Should raise a FileNotFoundError)
    - a remote zip file with only one valid hosts file
    - a local text file with valid hosts
    - a remote text file without valid hosts format.
    """
    # remote zip file with 1 hosts file and 2 useless files
    file1 = create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                             name='README', line_format='not_correct')
    file2 = create_blocklist(directory, blocked_hosts=BLOCKLIST_HOSTS[:3],
                             name='hosts', line_format='etc_hosts')
    file3 = create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                             name='false_positive', line_format='one_per_line')
    files_to_zip = [file1, file2, file3]
    blocklist1 = QUrl(create_zipfile(directory, files_to_zip, 'block1'))

    # remote zip file without file named hosts
    # (Should raise a FileNotFoundError)
    file1 = create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                             name='md5sum', line_format='etc_hosts')
    file2 = create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                             name='README', line_format='not_correct')
    file3 = create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                             name='false_positive', line_format='one_per_line')
    files_to_zip = [file1, file2, file3]
    blocklist2 = QUrl(create_zipfile(directory, files_to_zip, 'block2'))

    # remote zip file with only one valid hosts file inside
    blocklist3 = create_blocklist(directory,
                                  blocked_hosts=[BLOCKLIST_HOSTS[3]],
                                  name='malwarelist', line_format='etc_hosts')
    blocklist3 = QUrl(create_zipfile(directory, [blocklist3], 'block3'))

    # local text file with valid hosts
    blocklist4 = QUrl(create_blocklist(directory,
                                       blocked_hosts=[BLOCKLIST_HOSTS[4]],
                                       name='mycustomblocklist',
                                       line_format='one_per_line'))
    blocklist4.setScheme('file')

    # remote text file without valid hosts format
    blocklist5 = QUrl(create_blocklist(directory, blocked_hosts=CLEAN_HOSTS,
                                       name='notcorrectlist',
                                       line_format='not_correct'))

    return [blocklist1, blocklist2, blocklist3, blocklist4, blocklist5]


def test_without_datadir(config_stub, tmpdir, monkeypatch, win_registry):
    """No directory for data configured so no hosts file exists.

    Ensure CommandError is raised and no URL is blocked.
    """
    config_stub.data = {
        'content': {
            'host-block-lists': generic_blocklists(tmpdir),
            'host-blocking-enabled': True,
        }
    }
    monkeypatch.setattr('qutebrowser.utils.standarddir.data', lambda: None)
    host_blocker = adblock.HostBlocker()

    with pytest.raises(cmdexc.CommandError) as excinfo:
        host_blocker.adblock_update(0)
    assert str(excinfo.value) == "No data storage is configured!"

    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))

    # To test on_config_changed
    config_stub.set('content', 'host-block-lists', None)


def test_disabled_blocking_update(basedir, config_stub, download_stub,
                                  data_tmpdir, tmpdir, win_registry):
    """Ensure no URL is blocked when host blocking is disabled."""
    config_stub.data = {
        'content': {
            'host-block-lists': generic_blocklists(tmpdir),
            'host-blocking-enabled': False,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    while host_blocker._in_progress:
        current_download = host_blocker._in_progress[0]
        current_download.finished.emit()
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))


def test_no_blocklist_update(config_stub, download_stub,
                             data_tmpdir, basedir, tmpdir, win_registry):
    """Ensure no URL is blocked when no block list exists."""
    config_stub.data = {
        'content': {
            'host-block-lists': None,
            'host-blocking-enabled': True,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))


def test_successful_update(config_stub, basedir, download_stub,
                           data_tmpdir, tmpdir, win_registry):
    """Ensure hosts from host-block-lists are blocked after an update."""
    config_stub.data = {
        'content': {
            'host-block-lists': generic_blocklists(tmpdir),
            'host-blocking-enabled': True,
            'host-blocking-whitelist': None,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    # Simulate download is finished
    while host_blocker._in_progress:
        current_download = host_blocker._in_progress[0]
        current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted=[])


def test_failed_dl_update(config_stub, basedir, download_stub,
                          data_tmpdir, tmpdir, win_registry):
    """One blocklist fails to download.

    Ensure hosts from this list are not blocked.
    """
    dl_fail_blocklist = QUrl(create_blocklist(tmpdir,
                                              blocked_hosts=CLEAN_HOSTS,
                                              name='download_will_fail',
                                              line_format='one_per_line'))
    hosts_to_block = generic_blocklists(tmpdir) + [dl_fail_blocklist]
    config_stub.data = {
        'content': {
            'host-block-lists': hosts_to_block,
            'host-blocking-enabled': True,
            'host-blocking-whitelist': None,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    while host_blocker._in_progress:
        current_download = host_blocker._in_progress[0]
        # if current download is the file we want to fail, make it fail
        if current_download.name == dl_fail_blocklist.path():
            current_download.successful = False
        current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted=[])


def test_blocking_with_whitelist(config_stub, basedir, download_stub,
                                 data_tmpdir, tmpdir):
    """Ensure hosts in host-blocking-whitelist are never blocked."""
    # Simulate adblock_update has already been run
    # by creating a file named blocked-hosts,
    # Exclude localhost from it, since localhost is in HostBlocker.WHITELISTED
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]
    blocklist = create_blocklist(data_tmpdir,
                                 blocked_hosts=filtered_blocked_hosts,
                                 name='blocked-hosts',
                                 line_format='one_per_line')
    config_stub.data = {
        'content': {
            'host-block-lists': [blocklist],
            'host-blocking-enabled': True,
            'host-blocking-whitelist': WHITELISTED_HOSTS,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.read_hosts()
    assert_urls(host_blocker)


def test_config_change_initial(config_stub, basedir, download_stub,
                               data_tmpdir, tmpdir):
    """Test emptying host-block-lists on restart with existing blocked_hosts.

    - A blocklist is present in host-block-lists and blocked_hosts is populated
    - User quits qutebrowser, empties host-block-lists from his config
    - User restarts qutebrowser, does adblock-update
    """
    create_blocklist(tmpdir, blocked_hosts=BLOCKLIST_HOSTS,
                     name='blocked-hosts', line_format='one_per_line')
    config_stub.data = {
        'content': {
            'host-block-lists': None,
            'host-blocking-enabled': True,
            'host-blocking-whitelist': None,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))


def test_config_change(config_stub, basedir, download_stub,
                       data_tmpdir, tmpdir):
    """Ensure blocked-hosts resets if host-block-list is changed to None."""
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]  # Exclude localhost
    blocklist = QUrl(create_blocklist(tmpdir,
                                      blocked_hosts=filtered_blocked_hosts,
                                      name='blocked-hosts',
                                      line_format='one_per_line'))
    config_stub.data = {
        'content': {
            'host-block-lists': [blocklist],
            'host-blocking-enabled': True,
            'host-blocking-whitelist': None,
        }
    }
    host_blocker = adblock.HostBlocker()
    host_blocker.read_hosts()
    config_stub.set('content', 'host-block-lists', None)
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))
