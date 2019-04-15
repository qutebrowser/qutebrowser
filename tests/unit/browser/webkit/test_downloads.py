# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from qutebrowser.browser import downloads, qtnetworkdownloads
from qutebrowser.utils import objreg


def test_download_model(qapp, qtmodeltester, config_stub, cookiejar_and_cache,
                        fake_args):
    """Simple check for download model internals."""
    manager = qtnetworkdownloads.DownloadManager()
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
    item = downloads.AbstractDownloadItem()

    # Don't try to start a timer outside of a QThread
    manager._update_timer.isActive = lambda: True

    # Abstract methods
    item._ensure_can_set_filename = lambda *args: True
    item._after_set_filename = lambda *args: True

    # Don't try to get current window
    monkeypatch.setattr(item, '_get_conflicting_downloads', list)

    manager._init_item(item, True, raw)
    item.set_target(target)
    assert item._filename.endswith(expected)


class TestConflictingDownloads:

    def test_no_downloads(self, qapp, qtmodeltester, config_stub,
                          cookiejar_and_cache, fake_args, monkeypatch):
        my_item = downloads.AbstractDownloadItem()
        my_item._filename = 'download.txt'
        manager = qtnetworkdownloads.DownloadManager()
        model = downloads.DownloadModel(manager)
        monkeypatch.setattr(objreg, 'get', lambda *args, **kwargs: model)
        assert my_item._get_conflicting_downloads() == []

    def test_different_name(self, qapp, qtmodeltester, config_stub,
                            cookiejar_and_cache, fake_args, monkeypatch):
        my_item = downloads.AbstractDownloadItem()
        my_item._filename = 'download.txt'
        item2 = downloads.AbstractDownloadItem()
        item2._filename = 'download2.txt'
        item2.done = False
        manager = qtnetworkdownloads.DownloadManager()
        model = downloads.DownloadModel(manager)
        monkeypatch.setattr(objreg, 'get', lambda *args, **kwargs: model)
        monkeypatch.setattr(model, '_all_downloads',
                            lambda *args, **kwargs: [item2])
        assert my_item._get_conflicting_downloads() == []

    def test_finished_download(self, qapp, qtmodeltester, config_stub,
                               cookiejar_and_cache, fake_args, monkeypatch):
        my_item = downloads.AbstractDownloadItem()
        my_item._filename = 'download.txt'
        item2 = downloads.AbstractDownloadItem()
        item2._filename = 'download.txt'
        item2.done = True
        manager = qtnetworkdownloads.DownloadManager()
        model = downloads.DownloadModel(manager)
        monkeypatch.setattr(objreg, 'get', lambda *args, **kwargs: model)
        monkeypatch.setattr(model, '_all_downloads',
                            lambda *args, **kwargs: [item2])
        assert my_item._get_conflicting_downloads() == []

    def test_conflicting_downloads(self, qapp, qtmodeltester, config_stub,
                                   cookiejar_and_cache, fake_args,
                                   monkeypatch):
        my_item = downloads.AbstractDownloadItem()
        my_item._filename = 'download.txt'
        item2 = downloads.AbstractDownloadItem()
        item2._filename = 'download.txt'
        item2.done = False
        manager = qtnetworkdownloads.DownloadManager()
        model = downloads.DownloadModel(manager)
        monkeypatch.setattr(objreg, 'get', lambda *args, **kwargs: model)
        monkeypatch.setattr(model, '_all_downloads',
                            lambda *args, **kwargs: [item2])
        assert my_item._get_conflicting_downloads() == [item2]

    def test_cancel_conflicting_downloads(self, qapp, qtmodeltester,
                                          config_stub, cookiejar_and_cache,
                                          fake_args, monkeypatch):
        my_item = downloads.AbstractDownloadItem()
        my_item._filename = 'download.txt'
        item2 = downloads.AbstractDownloadItem()
        item2._filename = 'download.txt'
        item2.done = False
        manager = qtnetworkdownloads.DownloadManager()
        model = downloads.DownloadModel(manager)
        monkeypatch.setattr(objreg, 'get', lambda *args, **kwargs: model)

        def patched_cancel(remove_data=True):
            assert not remove_data
            item2.done = True

        monkeypatch.setattr(model, '_all_downloads',
                            lambda *args, **kwargs: [item2])
        monkeypatch.setattr(item2, 'cancel', patched_cancel)
        monkeypatch.setattr(my_item, '_after_set_filename', lambda: None)
        my_item._cancel_conflicting_downloads()
        assert item2.done
