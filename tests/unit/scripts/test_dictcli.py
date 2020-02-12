# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The-Compiler) <me@the-compiler.org>
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
        code='af-ZA',
        name='Afrikaans (South Africa)',
        remote_filename='af-ZA-3-0.bdic')


def english():
    return dictcli.Language(
        code='en-US',
        name='English (United States)',
        remote_filename='en-US-7-1.bdic')


def polish():
    return dictcli.Language(
        code='pl-PL',
        name='Polish (Poland)',
        remote_filename='pl-PL-3-0.bdic')


def langs():
    return [afrikaans(), english(), polish()]


@pytest.fixture(autouse=True)
def configdata_init():
    if configdata.DATA is None:
        configdata.init()


@pytest.fixture(autouse=True)
def dict_tmpdir(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    return tmpdir


def test_language(dict_tmpdir):
    (dict_tmpdir / 'pl-PL-2-0.bdic').ensure()
    assert english().local_filename is None
    assert polish()


def test_parse_entry():
    assert (dictcli.parse_entry({'name': 'en-US-7-1.bdic'}) ==
            ('en-US', 'en-US-7-1.bdic'))


def test_latest_yet():
    code2file = {'en-US': 'en-US-7-1.bdic'}
    assert not dictcli.latest_yet(code2file, 'en-US', 'en-US-7-0.bdic')
    assert not dictcli.latest_yet(code2file, 'en-US', 'en-US-7-1.bdic')
    assert dictcli.latest_yet(code2file, 'en-US', 'en-US-8-0.bdic')


def test_available_languages(dict_tmpdir, monkeypatch):
    for f in ['pl-PL-2-0.bdic', english().remote_filename]:
        (dict_tmpdir / f).ensure()
    monkeypatch.setattr(dictcli, 'language_list_from_api', lambda: [
        (lang.code, lang.remote_filename) for lang in langs()
    ])
    assert sorted(dictcli.available_languages()) == [
        dictcli.Language(
            code='af-ZA',
            name='Afrikaans (South Africa)',
            remote_filename='af-ZA-3-0.bdic',
            local_filename=None),
        dictcli.Language(
            code='en-US',
            name='English (United States)',
            remote_filename='en-US-7-1.bdic',
            local_filename=None),
        dictcli.Language(
            code='pl-PL',
            name='Polish (Poland)',
            remote_filename='pl-PL-3-0.bdic',
            local_filename='pl-PL-2-0.bdic'),
    ]


def test_filter_languages():
    filtered_langs = dictcli.filter_languages(langs(), ['af-ZA'])
    assert filtered_langs == [afrikaans()]

    filtered_langs = dictcli.filter_languages(langs(), ['pl-PL', 'en-US'])
    assert filtered_langs == [english(), polish()]

    with pytest.raises(dictcli.InvalidLanguageError):
        dictcli.filter_languages(langs(), ['pl-PL', 'en-GB'])


def test_install(dict_tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member

    # when
    dictcli.install(langs())

    # then
    installed_files = [f.basename for f in dict_tmpdir.listdir()]
    expected_files = [lang.remote_filename for lang in langs()]
    assert sorted(installed_files) == sorted(expected_files)


def test_update(dict_tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member
    (dict_tmpdir / 'pl-PL-2-0.bdic').ensure()
    assert polish().local_version < polish().remote_version

    # when
    dictcli.update(langs())

    # then
    assert polish().local_version == polish().remote_version


def test_remove_old(dict_tmpdir, monkeypatch):
    # given
    monkeypatch.setattr(
        dictcli, 'download_dictionary',
        lambda _url, dest: py.path.local(dest).ensure())  # pylint: disable=no-member
    for f in ['pl-PL-2-0.bdic',
              polish().remote_filename,
              english().remote_filename]:
        (dict_tmpdir / f).ensure()

    # when
    dictcli.remove_old(langs())

    # then
    installed_files = [f.basename for f in dict_tmpdir.listdir()]
    expected_files = [polish().remote_filename, english().remote_filename]
    assert sorted(installed_files) == sorted(expected_files)
