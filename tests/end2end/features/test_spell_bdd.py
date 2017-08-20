# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Michał Siedlaczek <michal.siedlaczek@gmail.com>
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

import pytest_bdd as bdd

bdd.scenarios('spell.feature')


@bdd.given(bdd.parsers.parse("spell check is {val}"))
def spellcheck_enabled_given(quteproc, val):
    enabled = val == 'on'
    quteproc.send_cmd(':debug-pyeval QWebEngineProfile.defaultProfile()' +
                      '.setSpellCheckEnabled({})'.format(enabled))
    quteproc.wait_for_load_finished('qute://pyeval')


@bdd.given(bdd.parsers.parse("spell check languages are {langs}"))
def spellcheck_langs_given(quteproc, langs):
    quteproc.send_cmd(':debug-pyeval QWebEngineProfile.defaultProfile()' +
                      '.setSpellCheckLanguages({})'.format(langs))
    quteproc.wait_for_load_finished('qute://pyeval')


@bdd.then(bdd.parsers.parse("spell check is {val}"))
def spellcheck_enabled_then(quteproc, val):
    quteproc.send_cmd(':debug-pyeval QWebEngineProfile.defaultProfile()' +
                      '.isSpellCheckEnabled()')
    quteproc.wait_for_load_finished('qute://pyeval')
    content = quteproc.get_content().strip()
    if val == 'on':
        assert content == 'True'
    else:
        assert content == 'False'


@bdd.then(bdd.parsers.parse("actual spell check languages are {langs}"))
def spellcheck_langs_then(quteproc, langs):
    quteproc.send_cmd(':debug-pyeval QWebEngineProfile.defaultProfile()' +
                      '.spellCheckLanguages()')
    quteproc.wait_for_load_finished('qute://pyeval')
    actual_langs = quteproc.get_content().strip()
    assert actual_langs == langs
