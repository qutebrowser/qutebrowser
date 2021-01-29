# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from qutebrowser.browser import downloads, qtnetworkdownloads


@pytest.fixture
def manager(config_stub, cookiejar_and_cache):
    """A QtNetwork download manager."""
    return qtnetworkdownloads.DownloadManager()


def test_download_model(qapp, qtmodeltester, manager):
    """Simple check for download model internals."""
    model = downloads.DownloadModel(manager)
    qtmodeltester.check(model)


@pytest.mark.parametrize('url, title, out', [
    ('http://qutebrowser.org/INSTALL.html',
     'Installing qutebrowser | qutebrowser',
     'Installing qutebrowser _ qutebrowser.html'),
    ('http://qutebrowser.org/INSTALL.html',
     'Installing qutebrowser | qutebrowser.html',
     'Installing qutebrowser _ qutebrowser.html'),
    ('http://qutebrowser.org/INSTALL.HTML',
     'Installing qutebrowser | qutebrowser',
     'Installing qutebrowser _ qutebrowser.html'),
    ('http://qutebrowser.org/INSTALL.html',
     'Installing qutebrowser | qutebrowser.HTML',
     'Installing qutebrowser _ qutebrowser.HTML'),
    ('http://qutebrowser.org/',
     'qutebrowser | qutebrowser',
     'qutebrowser _ qutebrowser.html'),
    ('https://github.com/qutebrowser/qutebrowser/releases',
     'Releases · qutebrowser/qutebrowser',
     'Releases · qutebrowser_qutebrowser.html'),
    ('http://qutebrowser.org/index.php',
     'qutebrowser | qutebrowser',
     'qutebrowser _ qutebrowser.html'),
    ('http://qutebrowser.org/index.php',
     'qutebrowser | qutebrowser - index.php',
     'qutebrowser _ qutebrowser - index.php.html'),
    ('https://qutebrowser.org/img/cheatsheet-big.png',
     'cheatsheet-big.png (3342×2060)',
     None),
    ('http://qutebrowser.org/page-with-no-title.html',
     '',
     None),
])
@pytest.mark.fake_os('windows')
def test_page_titles(url, title, out):
    assert downloads.suggested_fn_from_title(url, title) == out


class TestDownloadTarget:

    def test_filename(self):
        target = downloads.FileDownloadTarget("/foo/bar")
        assert target.filename == "/foo/bar"

    def test_fileobj(self):
        fobj = object()
        target = downloads.FileObjDownloadTarget(fobj)
        assert target.fileobj is fobj

    def test_openfile(self):
        target = downloads.OpenFileDownloadTarget()
        assert target.cmdline is None

    def test_openfile_custom_command(self):
        target = downloads.OpenFileDownloadTarget('echo')
        assert target.cmdline == 'echo'

    @pytest.mark.parametrize('obj', [
        downloads.FileDownloadTarget('foobar'),
        downloads.FileObjDownloadTarget(None),
        downloads.OpenFileDownloadTarget(),
    ])
    def test_class_hierarchy(self, obj):
        assert isinstance(obj, downloads._DownloadTarget)


@pytest.mark.parametrize('raw, expected', [
    pytest.param('http://foo/bar', 'bar',
                 marks=pytest.mark.fake_os('windows')),
    pytest.param('A *|<>\\: bear!', 'A ______ bear!',
                 marks=pytest.mark.fake_os('windows')),
    pytest.param('A *|<>\\: bear!', 'A *|<>\\: bear!',
                 marks=[pytest.mark.fake_os('posix'), pytest.mark.posix]),
])
def test_sanitized_filenames(raw, expected,
                             config_stub, download_tmpdir, monkeypatch):
    manager = downloads.AbstractDownloadManager()
    target = downloads.FileDownloadTarget(str(download_tmpdir))
    item = downloads.AbstractDownloadItem(manager=manager)

    # Don't try to start a timer outside of a QThread
    manager._update_timer.isActive = lambda: True

    # Abstract methods
    item._ensure_can_set_filename = lambda *args: True
    item._after_set_filename = lambda *args: True

    # Don't try to get current window
    monkeypatch.setattr(item, '_get_conflicting_download', list)

    manager._init_item(item, True, raw)
    item.set_target(target)
    assert item._filename.endswith(expected)


class TestConflictingDownloads:

    @pytest.fixture
    def item1(self, manager):
        return downloads.AbstractDownloadItem(manager=manager)

    @pytest.fixture
    def item2(self, manager):
        return downloads.AbstractDownloadItem(manager=manager)

    def test_no_downloads(self, item1):
        item1._filename = 'download.txt'
        assert item1._get_conflicting_download() is None

    @pytest.mark.parametrize('filename1, filename2, done, conflict', [
        # Different name
        ('download.txt', 'download2.txt', False, False),
        # Finished
        ('download.txt', 'download.txt', True, False),
        # Conflict
        ('download.txt', 'download.txt', False, True),
    ])
    def test_conflicts(self, manager, item1, item2,
                       filename1, filename2, done, conflict):
        item1._filename = filename1
        item2._filename = filename2
        item2.done = done
        manager.downloads.append(item1)
        manager.downloads.append(item2)
        expected = item2 if conflict else None
        assert item1._get_conflicting_download() is expected

    def test_cancel_conflicting_downloads(self, manager, item1, item2, monkeypatch):
        item1._filename = 'download.txt'
        item2._filename = 'download.txt'
        item2.done = False
        manager.downloads.append(item1)
        manager.downloads.append(item2)

        def patched_cancel(remove_data=True):
            assert not remove_data
            item2.done = True

        monkeypatch.setattr(item2, 'cancel', patched_cancel)
        monkeypatch.setattr(item1, '_after_set_filename', lambda: None)
        item1._cancel_conflicting_download()
        assert item2.done
