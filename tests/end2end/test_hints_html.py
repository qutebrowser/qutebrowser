# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import textwrap
import string
import functools
import operator

import attr
import yaml
import pytest
import bs4

import qutebrowser.browser.hints


def collect_tests():
    basedir = os.path.dirname(__file__)
    datadir = os.path.join(basedir, 'data', 'hints', 'html')
    files = [f for f in os.listdir(datadir) if f != 'README.md']
    return files


@attr.s
class ParsedFile:

    target = attr.ib()
    qtwebengine_todo = attr.ib()


class InvalidFile(Exception):

    def __init__(self, test_name, msg):
        super().__init__("Invalid comment found in {}, please read "
                         "tests/end2end/data/hints/html/README.md - {}".format(
                             test_name, msg))


def _parse_file(test_name):
    """Parse the given HTML file."""
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'data', 'hints', 'html', test_name)
    with open(file_path, 'r', encoding='utf-8') as html:
        soup = bs4.BeautifulSoup(html, 'html.parser')

    comment = soup.find(text=lambda text: isinstance(text, bs4.Comment))

    if comment is None:
        raise InvalidFile(test_name, "no comment found")

    data = yaml.load(comment)
    if not isinstance(data, dict):
        raise InvalidFile(test_name, "expected yaml dict but got {}".format(
            type(data).__name__))

    allowed_keys = {'target', 'qtwebengine_todo'}
    if not set(data.keys()).issubset(allowed_keys):
        raise InvalidFile(test_name, "expected keys {} but found {}".format(
                          ', '.join(allowed_keys),
                          ', '.join(set(data.keys()))))

    if 'target' not in data:
        raise InvalidFile(test_name, "'target' key not found")

    qtwebengine_todo = data.get('qtwebengine_todo', None)

    return ParsedFile(target=data['target'], qtwebengine_todo=qtwebengine_todo)


@pytest.mark.parametrize('test_name', collect_tests())
@pytest.mark.parametrize('zoom_text_only', [True, False])
@pytest.mark.parametrize('zoom_level', [100, 66, 33])
@pytest.mark.parametrize('find_implementation', ['javascript', 'python'])
def test_hints(test_name, zoom_text_only, zoom_level, find_implementation,
               quteproc, request):
    if zoom_text_only and request.config.webengine:
        pytest.skip("QtWebEngine doesn't have zoom.text_only")
    if find_implementation == 'python' and request.config.webengine:
        pytest.skip("QtWebEngine doesn't have a python find implementation")

    parsed = _parse_file(test_name)
    if parsed.qtwebengine_todo is not None and request.config.webengine:
        pytest.xfail("QtWebEngine TODO: {}".format(parsed.qtwebengine_todo))

    url_path = 'data/hints/html/{}'.format(test_name)
    quteproc.open_path(url_path)

    # setup
    if not request.config.webengine:
        quteproc.set_setting('zoom.text_only', str(zoom_text_only))
        quteproc.set_setting('hints.find_implementation', find_implementation)
    quteproc.send_cmd(':zoom {}'.format(zoom_level))
    # follow hint
    quteproc.send_cmd(':hint links normal')
    quteproc.wait_for(message='hints: a', category='hints')
    quteproc.send_cmd(':follow-hint a')
    quteproc.wait_for_load_finished('data/' + parsed.target)
    # reset
    quteproc.send_cmd(':zoom 100')
    if not request.config.webengine:
        quteproc.set_setting('zoom.text_only', 'false')
        quteproc.set_setting('hints.find_implementation', 'javascript')


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

    quteproc.set_setting('hints.mode', 'word')
    quteproc.set_setting('hints.dictionary', str(dict_file))

    for hint, target in targets:
        quteproc.open_path('data/hints/issue1393.html')
        quteproc.send_cmd(':hint')
        quteproc.wait_for(message='hints: *', category='hints')
        quteproc.send_cmd(':follow-hint {}'.format(hint))
        quteproc.wait_for_load_finished('data/{}'.format(target))


@pytest.mark.parametrize('min_len', [0, 3])
@pytest.mark.parametrize('num_chars', [9])
@pytest.mark.parametrize('num_elements', range(1, 26))
def test_scattered_hints_count(win_registry, mode_manager, min_len,
                               num_chars, num_elements):
    """Test scattered hints function.

    Tests many properties from an invocation of _hint_scattered, including

    1. Hints must be unique
    2. There can only be two hint lengths, only 1 apart
    3. There are no unique prefixes for long hints, such as 'la' with no 'l<x>'
    """
    manager = qutebrowser.browser.hints.HintManager(0, 0)
    chars = string.ascii_lowercase[:num_chars]

    hints = manager._hint_scattered(min_len, chars,
                                    list(range(num_elements)))

    # Check if hints are unique
    assert len(hints) == len(set(hints))

    # Check if any hints are shorter than min_len
    assert not any(x for x in hints if len(x) < min_len)

    # Check we don't have more than 2 link lengths
    # Eg: 'a' 'bc' and 'def' cannot be in the same hint string
    hint_lens = {len(h) for h in hints}
    assert len(hint_lens) <= 2

    if len(hint_lens) == 2:
        # Check if hint_lens are more than 1 apart
        # Eg: 'abc' and 'd' cannot be in the same hint sequence, but
        # 'ab' and 'c' can
        assert abs(functools.reduce(operator.sub, hint_lens)) <= 1

    longest_hints = [x for x in hints if len(x) == max(hint_lens)]

    if min_len < max(hint_lens) - 1:
        # Check if we have any unique prefixes. For example, 'la'
        # alone, with no other 'l<x>'
        count_map = {}
        for x in longest_hints:
            prefix = x[:-1]
            count_map[prefix] = count_map.get(prefix, 0) + 1
        assert all(e != 1 for e in count_map.values())
