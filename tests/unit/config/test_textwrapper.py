# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for config.textwrapper."""

from qutebrowser.config import textwrapper


def test_default_args():
    wrapper = textwrapper.TextWrapper()
    assert wrapper.width == 72
    assert not wrapper.replace_whitespace
    assert not wrapper.break_long_words
    assert not wrapper.break_on_hyphens
    assert wrapper.initial_indent == '# '
    assert wrapper.subsequent_indent == '# '


def test_custom_args():
    wrapper = textwrapper.TextWrapper(drop_whitespace=False)
    assert wrapper.width == 72
    assert not wrapper.drop_whitespace
