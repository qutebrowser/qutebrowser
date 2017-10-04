# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Michal Siedlaczek <michal.siedlaczek@gmail.com>

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


import py.path  # pylint: disable=no-name-in-module
import pytest

from qutebrowser.browser.webengine import spell
from scripts import install_dict
from qutebrowser.config import configdata

AFRIKAANS = install_dict.Language(
    'af-ZA',
    'Afrikaans (South Africa)',
    'af-ZA-3-0')
ENGLISH = install_dict.Language(
    'en-US',
    'English (United States)',
    'en-US-7-1')
POLISH = install_dict.Language(
    'pl-PL',
    'Polish (Poland)',
    'pl-PL-3-0')

LANGUAGE_LIST = [AFRIKAANS, ENGLISH, POLISH]


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


def test_filter_languages():
    filtered_langs = install_dict.filter_languages(LANGUAGE_LIST, ['af-ZA'])
    assert filtered_langs == [AFRIKAANS]

    filtered_langs = install_dict.filter_languages(
        LANGUAGE_LIST, ['pl-PL', 'en-US'])
    assert filtered_langs == [ENGLISH, POLISH]

    with pytest.raises(install_dict.InvalidLanguageError):
        install_dict.filter_languages(LANGUAGE_LIST, ['pl-PL', 'en-GB'])


def test_install(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    monkeypatch.setattr(
        install_dict, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member
    install_dict.install(LANGUAGE_LIST)
    installed_files = [f.basename for f in tmpdir.listdir()]
    expected_files = [lang.file_path for lang in LANGUAGE_LIST]
    assert sorted(installed_files) == sorted(expected_files)
