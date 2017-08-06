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


from os.path import basename

import pytest

from qutebrowser.browser.webengine import spell

AFRIKAANS = spell.Language('af-ZA',
                           'Afrikaans (South Africa)',
                           'af-ZA-3-0.bdic')
ENGLISH = spell.Language('en-US',
                         'English (United States)',
                         'en-US-7-1.bdic')
POLISH = spell.Language('pl-PL',
                        'Polish (Poland)',
                        'pl-PL-3-0.bdic')

LANGUAGE_LIST = [AFRIKAANS, ENGLISH, POLISH]


def test_get_available_languages():
    language_list = spell.get_available_languages()
    assert len(language_list) == 42
    first_lang = language_list[0]
    assert (first_lang.code, first_lang.name, first_lang.file) ==\
           (AFRIKAANS.code, AFRIKAANS.name, AFRIKAANS.file)


def test_filter_languages():
    filtered_languages = spell.filter_languages(LANGUAGE_LIST, ['af-ZA'])
    assert filtered_languages == [AFRIKAANS]
    filtered_languages = spell.filter_languages(LANGUAGE_LIST,
                                                ['pl-PL', 'en-US'])
    assert filtered_languages == [ENGLISH, POLISH]
    with pytest.raises(ValueError):
        spell.filter_languages(LANGUAGE_LIST, ['pl-PL', 'en-GB'])
    filtered_languages = spell.filter_languages(LANGUAGE_LIST,
                                                ['pl-PL-3-0.bdic'],
                                                by=lambda lang: lang.file)
    assert filtered_languages == [POLISH]


def test_install(tmpdir, mocker):
    mocker.patch('qutebrowser.browser.webengine.spell.get_dictionary_dir',
                 lambda: str(tmpdir))
    all_languages = spell.get_available_languages()
    spell.install(all_languages)
    installed_files = [basename(file) for file in tmpdir.listdir()]
    expected_files = [lang.file for lang in all_languages]
    assert sorted(installed_files) == sorted(expected_files)
