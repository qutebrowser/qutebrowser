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


WHITELISTED_HOSTS = ('qutebrowser.org', 'mediumhost.io')

BLOCKLIST_HOSTS = ('localhost',
                   'mediumhost.io',
                   'malware.badhost.org',
                   '4-verybadhost.com',
                   'ads.worsthostever.net')

CLEAN_HOSTS = ('goodhost.gov', 'verygoodhost.com')

URLS_TO_CHECK = ('http://localhost',
                 'http://mediumhost.io',
                 'http://malware.badhost.org',
                 'http://4-verybadhost.com',
                 'http://ads.worsthostever.net',
                 'http://goodhost.gov',
                 'ftp://verygoodhost.com'
                 'http://qutebrowser.org')


@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):

    """Set tmpdir as datadir"""

    tmpdir = str(tmpdir)
    monkeypatch.setattr('qutebrowser.utils.standarddir.data', lambda: tmpdir)


# XXX Why does read_hosts needs basedir to be None
# in order to print message 'run adblock-update to read host blocklist' ?
# browser/adblock.py line 138
class BaseDirStub:

    """Mock for objreg.get('args') called in adblock.HostBlocker.read_hosts."""

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

    def __init__(self, fileobj, name):
        super().__init__()
        self.fileobj = fileobj
        self.name = name
        self.successful = True


class FakeDownloadManager:

    """Mock browser.downloads.DownloadManager."""

    def get(self, url, fileobj, **kwargs):

        """Return a FakeDownloadItem instance with a fileobj
           whose content is copied from the file the given url links to.
        """

        download_item = FakeDownloadItem(fileobj, name=url.path())
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


def create_zipfile(directory, files, zipname='test'):

    """Return a path to a created zip file

       Args :
       - directory : path object where to create the zip file
       - files : list of paths to each file to add in the zipfile
       - zipname : name to give to the zip file.
    """

    directory = str(directory)
    zipfile_path = os.path.join(directory, zipname + '.zip')
    with zipfile.ZipFile(zipfile_path, 'w') as new_zipfile:
        for file_name in files:
            new_zipfile.write(file_name, arcname=os.path.basename(file_name))
            # Removes path from file name
    return zipfile_path


def create_blocklist(directory,
                     blocked_hosts=BLOCKLIST_HOSTS,
                     name='hosts',
                     line_format='one_per_line'):

    """Return a QUrl instance linking to a blocklist file.

       Args:
         - directory : path object where to create the blocklist file
         - blocked_hosts : an iterable of string hosts to add to the blocklist
         - name : name to give to the blocklist file
         - line_format : 'etc_hosts'  -->  /etc/hosts format
                         'one_per_line'  -->  one host per line format
                         'not_correct'  -->  Not a correct hosts file format.
    """

    blocklist = QUrl(os.path.join(str(directory), name))
    with open(blocklist.path(), 'w', encoding='UTF-8') as hosts:
        # ensure comments are ignored when processing blocklist
        hosts.write('# Blocked Hosts List #\n\n')
        if line_format == 'etc_hosts': # /etc/hosts like format
            for path in blocked_hosts:
                hosts.write('127.0.0.1  ' + path + '\n')
        elif line_format == 'one_per_line':
            for path in blocked_hosts:
                hosts.write(path + '\n')
        elif line_format == 'not_correct':
            for path in blocked_hosts:
                hosts.write(path + ' This is not a correct hosts file\n')
    return blocklist


def assert_urls(host_blocker,
                blocked=BLOCKLIST_HOSTS,
                whitelisted_hosts=WHITELISTED_HOSTS,
                urls_to_check=URLS_TO_CHECK):

    """Test if urls_to_check are effectively blocked or not by HostBlocker
       Ensure Urls in blocked and not in whitelisted are blocked
       All other Urls are not to be blocked."""

    whitelisted = list(whitelisted_hosts) + list(host_blocker.WHITELISTED)
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
       - a remote text file without valid hosts format."""

    # remote zip file with 1 hosts file and 2 useless files
    file1 = create_blocklist(directory,
                             blocked_hosts=CLEAN_HOSTS,
                             name='README',
                             line_format='not_correct')
    file2 = create_blocklist(directory,
                             blocked_hosts=BLOCKLIST_HOSTS[:3],
                             name='hosts',
                             line_format='etc_hosts')
    file3 = create_blocklist(directory,
                             blocked_hosts=CLEAN_HOSTS,
                             name='false_positive',
                             line_format='one_per_line')
    files_to_zip = [file1.path(), file2.path(), file3.path()]
    zip_path = create_zipfile(directory, files_to_zip, 'block1')
    blocklist1 = QUrl(zip_path)

    # remote zip file without file named hosts
    # (Should raise a FileNotFoundError)
    file1 = create_blocklist(directory,
                             blocked_hosts=CLEAN_HOSTS,
                             name='md5sum',
                             line_format='etc_hosts')
    file2 = create_blocklist(directory,
                             blocked_hosts=CLEAN_HOSTS,
                             name='README',
                             line_format='not_correct')
    file3 = create_blocklist(directory,
                             blocked_hosts=CLEAN_HOSTS,
                             name='false_positive',
                             line_format='one_per_line')
    files_to_zip = [file1.path(), file2.path(), file3.path()]
    zip_path = create_zipfile(directory, files_to_zip, 'block2')
    blocklist2 = QUrl(zip_path)

    # remote zip file with only one valid hosts file inside
    blocklist3 = create_blocklist(directory,
                                  blocked_hosts=[BLOCKLIST_HOSTS[3]],
                                  name='malwarelist',
                                  line_format='etc_hosts')
    zip_path = create_zipfile(directory, [blocklist3.path()], 'block3')
    blocklist3 = QUrl(zip_path)

    # local text file with valid hosts
    blocklist4 = create_blocklist(directory,
                                  blocked_hosts=[BLOCKLIST_HOSTS[4]],
                                  name='mycustomblocklist',
                                  line_format='one_per_line')
    blocklist4.setScheme('file')

    # remote text file without valid hosts format
    blocklist5 = create_blocklist(directory,
                                  blocked_hosts=CLEAN_HOSTS,
                                  name='notcorrectlist',
                                  line_format='not_correct')

    return [blocklist1, blocklist2, blocklist3, blocklist4, blocklist5]


def test_without_datadir(config_stub, tmpdir, monkeypatch, win_registry):

    """No directory for data configured so no hosts file exists.
       CommandError is raised by adblock_update
       Ensure no url is blocked."""

    config_stub.data = {'content':
                        {'host-block-lists': generic_blocklists(tmpdir),
                         'host-blocking-enabled': True}}
    monkeypatch.setattr('qutebrowser.utils.standarddir.data', lambda: None)
    host_blocker = adblock.HostBlocker()
    with pytest.raises(cmdexc.CommandError):
        host_blocker.adblock_update(0)
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))


def test_disabled_blocking_update(basedir, config_stub, download_stub,
                                  data_tmpdir, tmpdir, win_registry):

    """Ensure that no url is blocked when host blocking is disabled."""

    config_stub.data = {'content':
                        {'host-block-lists': generic_blocklists(tmpdir),
                         'host-blocking-enabled': False}}
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

    """Ensure no host is blocked when no blocklist exists."""

    config_stub.data = {'content':
                        {'host-block-lists' : None,
                         'host-blocking-enabled': True}}
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))


def test_successful_update(config_stub, basedir, download_stub,
                           data_tmpdir, tmpdir, win_registry):

    """Ensure hosts from host-block-lists are correctly
       blocked after update."""

    config_stub.data = {'content':
                        {'host-block-lists': generic_blocklists(tmpdir),
                         'host-blocking-enabled': True,
                         'host-blocking-whitelist': None}}
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    # Simulate download is finished
    # XXX Is it ok to use private list hostblocker._in_progress ?
    while host_blocker._in_progress:
        current_download = host_blocker._in_progress[0]
        current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted_hosts=[])


def test_failed_dl_update(config_stub, basedir, download_stub,
                          data_tmpdir, tmpdir, win_registry):

    """ One blocklist fails to download
        Ensure no hosts from this list is blocked."""

    dl_fail_blocklist = create_blocklist(tmpdir,
                                         blocked_hosts=CLEAN_HOSTS,
                                         name='download_will_fail',
                                         line_format='one_per_line')
    hosts_to_block = generic_blocklists(tmpdir) + [dl_fail_blocklist]
    config_stub.data = {'content':
                        {'host-block-lists': hosts_to_block,
                         'host-blocking-enabled': True,
                         'host-blocking-whitelist': None}}
    host_blocker = adblock.HostBlocker()
    host_blocker.adblock_update(0)
    while host_blocker._in_progress:
        current_download = host_blocker._in_progress[0]
        # if current download is the file we want to fail, make it fail
        if current_download.name == dl_fail_blocklist.path():
            current_download.successful = False
        current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted_hosts=[])


def test_blocking_with_whitelist(config_stub, basedir, download_stub,
                                 data_tmpdir, tmpdir):

    """Ensure hosts in host-blocking-whitelist are taken into account."""

    # Simulate adblock_update has already been run by naming it blocked-hosts,
    # exclude localhost from blocked-hosts file as it is in
    # host_blocker.WHITELISTED
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]
    blocklist = create_blocklist(tmpdir,
                                 blocked_hosts=filtered_blocked_hosts,
                                 name='blocked-hosts',
                                 line_format='one_per_line')
    config_stub.data = {'content':
                        {'host-block-lists': [blocklist],
                         'host-blocking-enabled': True,
                         'host-blocking-whitelist': WHITELISTED_HOSTS}}
    host_blocker = adblock.HostBlocker()
    host_blocker.read_hosts()
    assert_urls(host_blocker)


# XXX Intended behavior ?
# User runs qutebrowser with host-blocking enabled
# A blocklist is present in host-block-lists and blocked_hosts is populated
#
# User quits qutebrowser, empties host-block-lists from his config
# User restarts qutebrowser, does adblock-update (which will return None)
# read_hosts still returns hosts from unchanged blocked_hosts file
#
# Is this intended behavior or shouldn't on_config_changed be also called
# during HostBlocker instance init to avoid this ?
#
# As a comparison,
# host-block-lists is emptied with qutebrowser running
# on_config_changed slot is activated
# blocked_hosts is emptied
# read_hosts doesn't return any host as expected

def test_config_change(config_stub, basedir, download_stub,
                       data_tmpdir, tmpdir):

    """Ensure blocked_hosts gets a reset when host-block-list
       is changed to None."""

    # Simulate adblock_update has already been run by naming it blocked-hosts,
    # exclude localhost from blocked-hosts file as it is in
    # host_blocker.WHITELISTED
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]
    blocklist = create_blocklist(tmpdir,
                                 blocked_hosts=filtered_blocked_hosts,
                                 name='blocked-hosts',
                                 line_format='one_per_line')
    config_stub.data = {'content':
                        {'host-block-lists': [blocklist],
                         'host-blocking-enabled': True,
                         'host-blocking-whitelist': None}}
    host_blocker = adblock.HostBlocker()
    host_blocker.read_hosts()
    config_stub.set('content', 'host-block-lists', None)
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker.is_blocked(QUrl(str_url))
