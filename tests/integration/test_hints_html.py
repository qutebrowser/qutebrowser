# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test hints based on html files with special comments."""

import os
import os.path

import yaml
import pytest
import bs4
import textwrap


def collect_tests():
    basedir = os.path.dirname(__file__)
    datadir = os.path.join(basedir, 'data', 'hints', 'html')
    files = os.listdir(datadir)
    return files


@pytest.mark.parametrize('test_name', collect_tests())
@pytest.mark.parametrize('zoom_text_only', [True, False])
@pytest.mark.parametrize('zoom_level', [100, 66, 33])
def test_hints(test_name, zoom_text_only, zoom_level, quteproc):
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'data', 'hints', 'html', test_name)
    url_path = 'data/hints/html/{}'.format(test_name)
    quteproc.open_path(url_path)

    with open(file_path, 'r', encoding='utf-8') as html:
        soup = bs4.BeautifulSoup(html, 'html.parser')

    comment = soup.find(text=lambda text: isinstance(text, bs4.Comment))
    parsed = yaml.load(comment)

    assert set(parsed.keys()) == {'target'}

    # setup
    quteproc.send_cmd(':set ui zoom-text-only {}'.format(zoom_text_only))
    quteproc.send_cmd(':zoom {}'.format(zoom_level))
    # follow hint
    quteproc.send_cmd(':hint links normal')
    quteproc.wait_for(message='hints: a', category='hints')
    quteproc.send_cmd(':follow-hint a')
    quteproc.wait_for_load_finished('data/' + parsed['target'])
    # reset
    quteproc.send_cmd(':zoom 100')
    quteproc.send_cmd(':set ui zoom-text-only false')


def test_word_hints_issue1393(quteproc, tmpdir):
    dict_file = tmpdir / 'dict'
    dict_file.write(textwrap.dedent("""
        alph
        beta
        gamm
        delt
        epsi
    """))
    targets = [
        ('words', 'words.txt'),
        ('smart', 'smart.txt'),
        ('hinting', 'hinting.txt'),
        ('alph', 'l33t.txt'),
        ('beta', 'l33t.txt'),
        ('gamm', 'l33t.txt'),
        ('delt', 'l33t.txt'),
        ('epsi', 'l33t.txt'),
    ]

    quteproc.set_setting('hints', 'mode', 'word')
    quteproc.set_setting('hints', 'dictionary', str(dict_file))

    for hint, target in targets:
        quteproc.open_path('data/hints/issue1393.html')
        quteproc.send_cmd(':hint')
        quteproc.wait_for(message='hints: *', category='hints')
        quteproc.send_cmd(':follow-hint {}'.format(hint))
        quteproc.wait_for_load_finished('data/{}'.format(target))
