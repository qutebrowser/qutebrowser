# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2017-2018 Michal Siedlaczek <michal.siedlaczek@gmail.com>

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

import logging
import os

import pytest
from PyQt5.QtCore import QLibraryInfo

from qutebrowser.browser.webengine import spell
from qutebrowser.utils import usertypes, qtutils, standarddir


def test_version(message_mock, caplog):
    """Tests parsing dictionary version from its file name."""
    assert spell.version('en-US-8-0.bdic') == (8, 0)
    assert spell.version('pl-PL-3-0.bdic') == (3, 0)
    with caplog.at_level(logging.WARNING):
        assert spell.version('malformed_filename') is None
    msg = message_mock.getmsg(usertypes.MessageLevel.warning)
    expected = ("Found a dictionary with a malformed name: malformed_filename")
    assert msg.text == expected


@pytest.mark.parametrize('qt_version, old, subdir', [
    ('5.9', True, 'global_datapath'),
    ('5.9', False, 'global_datapath'),
    ('5.10', True, 'global_datapath'),
    ('5.10', False, 'user_datapath'),
])
def test_dictionary_dir(monkeypatch, qt_version, old, subdir):
    monkeypatch.setattr(qtutils, 'qVersion', lambda: qt_version)
    monkeypatch.setattr(QLibraryInfo, 'location', lambda _: 'global_datapath')
    monkeypatch.setattr(standarddir, 'data', lambda: 'user_datapath')

    expected = os.path.join(subdir, 'qtwebengine_dictionaries')
    assert spell.dictionary_dir(old=old) == expected


def test_local_filename_dictionary_does_not_exist(monkeypatch):
    """Tests retrieving local filename when the dir doesn't exits."""
    monkeypatch.setattr(
        spell, 'dictionary_dir', lambda: '/some-non-existing-dir')
    assert not spell.local_filename('en-US')


def test_local_filename_dictionary_not_installed(tmpdir, monkeypatch):
    """Tests retrieving local filename when the dict not installed."""
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    assert not spell.local_filename('en-US')


def test_local_filename_not_installed_malformed(tmpdir, monkeypatch, caplog):
    """Tests retrieving local filename when the only file is malformed."""
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    (tmpdir / 'en-US.bdic').ensure()
    with caplog.at_level(logging.WARNING):
        assert not spell.local_filename('en-US')


def test_local_filename_dictionary_installed(tmpdir, monkeypatch):
    """Tests retrieving local filename when the dict installed."""
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    for lang_file in ['en-US-11-0.bdic', 'en-US-7-1.bdic', 'pl-PL-3-0.bdic']:
        (tmpdir / lang_file).ensure()
    assert spell.local_filename('en-US') == 'en-US-11-0.bdic'
    assert spell.local_filename('pl-PL') == 'pl-PL-3-0.bdic'


def test_local_filename_installed_malformed(tmpdir, monkeypatch, caplog):
    """Tests retrieving local filename when the dict installed.

    In this usecase, another existing file is malformed."""
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    for lang_file in ['en-US-11-0.bdic', 'en-US-7-1.bdic', 'en-US.bdic']:
        (tmpdir / lang_file).ensure()
    with caplog.at_level(logging.WARNING):
        assert spell.local_filename('en-US') == 'en-US-11-0.bdic'


class TestInit:

    ENV = 'QTWEBENGINE_DICTIONARIES_PATH'

    @pytest.fixture(autouse=True)
    def remove_envvar(self, monkeypatch):
        monkeypatch.delenv(self.ENV, raising=False)

    @pytest.fixture
    def patch_new_qt(self, monkeypatch):
        monkeypatch.setattr(spell.qtutils, 'version_check',
                            lambda _ver, compiled: True)

    @pytest.fixture
    def dict_dir(self, data_tmpdir):
        return data_tmpdir / 'qtwebengine_dictionaries'

    @pytest.fixture
    def old_dict_dir(self, monkeypatch, tmpdir):
        data_dir = tmpdir / 'old'
        dict_dir = data_dir / 'qtwebengine_dictionaries'
        (dict_dir / 'somedict').ensure()
        monkeypatch.setattr(spell.QLibraryInfo, 'location',
                            lambda _arg: str(data_dir))
        return dict_dir

    def test_old_qt(self, monkeypatch):
        monkeypatch.setattr(spell.qtutils, 'version_check',
                            lambda _ver, compiled: False)
        spell.init()
        assert self.ENV not in os.environ

    def test_new_qt(self, dict_dir, patch_new_qt):
        spell.init()
        assert os.environ[self.ENV] == str(dict_dir)

    def test_moving(self, old_dict_dir, dict_dir, patch_new_qt):
        spell.init()
        assert (dict_dir / 'somedict').exists()

    def test_moving_oserror(self, mocker, caplog,
                            old_dict_dir, dict_dir, patch_new_qt):
        mocker.patch('shutil.copytree', side_effect=OSError)

        with caplog.at_level(logging.ERROR):
            spell.init()

        assert caplog.messages[0] == 'Failed to copy old dictionaries'

    def test_moving_existing_destdir(self, old_dict_dir, dict_dir,
                                     patch_new_qt):
        dict_dir.ensure(dir=True)
        spell.init()
        assert not (dict_dir / 'somedict').exists()
