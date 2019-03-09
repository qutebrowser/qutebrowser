# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2019 Florian Bruhin (The-Compiler) <me@the-compiler.org>
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


import py.path  # pylint: disable=no-name-in-module
import pytest

from qutebrowser.browser.webengine import spell
from qutebrowser.config import configdata
from scripts import dictcli


def afrikaans():
    return dictcli.Language(
        'af-ZA',
        'Afrikaans (South Africa)',
        'af-ZA-3-0')


def english():
    return dictcli.Language(
        'en-US',
        'English (United States)',
        'en-US-7-1')


def polish():
    return dictcli.Language(
        'pl-PL',
        'Polish (Poland)',
        'pl-PL-3-0')


def langs():
    return [afrikaans(), english(), polish()]


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


def test_language(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    (tmpdir / 'pl-PL-2-0.bdic').ensure()
    assert english().local_filename is None
    assert english().local_path is None
    assert polish()


def test_parse_entry():
    assert dictcli.parse_entry({'name': 'en-US-7-1.bdic'}) == \
        ('en-US', 'en-US-7-1')


def test_latest_yet():
    code2file = {'en-US': 'en-US-7-1.bdic'}
    assert not dictcli.latest_yet(code2file, 'en-US', 'en-US-7-0.bdic')
    assert not dictcli.latest_yet(code2file, 'en-US', 'en-US-7-1.bdic')
    assert dictcli.latest_yet(code2file, 'en-US', 'en-US-8-0.bdic')


def test_available_languages(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    for f in ['pl-PL-2-0.bdic', english().remote_path]:
        (tmpdir / f).ensure()
    monkeypatch.setattr(dictcli, 'language_list_from_api', lambda: [
        (lang.code, lang.remote_filename) for lang in langs()
    ])
    assert sorted(dictcli.available_languages()) == [
        dictcli.Language(
            'af-ZA', 'Afrikaans (South Africa)',
            'af-ZA-3-0', None),
        dictcli.Language(
            'en-US', 'English (United States)',
            'en-US-7-1', 'en-US-7-1'),
        dictcli.Language(
            'pl-PL', 'Polish (Poland)',
            'pl-PL-3-0', 'pl-PL-2-0')
    ]


def test_filter_languages():
    filtered_langs = dictcli.filter_languages(langs(), ['af-ZA'])
    assert filtered_langs == [afrikaans()]

    filtered_langs = dictcli.filter_languages(langs(), ['pl-PL', 'en-US'])
    assert filtered_langs == [english(), polish()]

    with pytest.raises(dictcli.InvalidLanguageError):
        dictcli.filter_languages(langs(), ['pl-PL', 'en-GB'])


def test_install(tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member

    # when
    dictcli.install(langs())

    # then
    installed_files = [f.basename for f in tmpdir.listdir()]
    expected_files = [lang.remote_path for lang in langs()]
    assert sorted(installed_files) == sorted(expected_files)


def test_update(tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member
    (tmpdir / 'pl-PL-2-0.bdic').ensure()
    assert polish().local_version < polish().remote_version

    # when
    dictcli.update(langs())

    # then
    assert polish().local_version == polish().remote_version


def test_remove_old(tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member
    for f in ['pl-PL-2-0.bdic', polish().remote_path, english().remote_path]:
        (tmpdir / f).ensure()

    # when
    dictcli.remove_old(langs())

    # then
    installed_files = [f.basename for f in tmpdir.listdir()]
    expected_files = [polish().remote_path, english().remote_path]
    assert sorted(installed_files) == sorted(expected_files)
