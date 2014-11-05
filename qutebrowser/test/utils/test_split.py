# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.split."""

import unittest

from qutebrowser.utils import split


# Most tests copied from Python's shlex.
# The original test data set was from shellwords, by Hartmut Goebel.

# Format: input/split|output|without|keep/split|output|with|keep/

test_data = r"""
one two/one|two/one |two/
one "two three" four/one|two three|four/one |"two three" |four/
one 'two three' four/one|two three|four/one |'two three' |four/
one "two\" three" four/one|two" three|four/one |"two\" three" |four/
one 'two'\'' three' four/one|two' three|four/one |'two'\'' three' |four/
one "two three/one|two three/one |"two three/
one 'two three/one|two three/one |'two three/
one\/one\/one\/
one "two\/one|two\/one |"two\/
foo bar/foo|bar/foo |bar/
 foo bar/foo|bar/ foo |bar/
 foo bar /foo|bar/ foo |bar /
foo   bar    bla     fasel/foo|bar|bla|fasel/foo   |bar    |bla     |fasel/
x y  z              xxxx/x|y|z|xxxx/x |y  |z              |xxxx/
\x bar/x|bar/\x |bar/
\ x bar/ x|bar/\ x |bar/
\ bar/ bar/\ bar/
foo \x bar/foo|x|bar/foo |\x |bar/
foo \ x bar/foo| x|bar/foo |\ x |bar/
foo \ bar/foo| bar/foo |\ bar/
foo "bar" bla/foo|bar|bla/foo |"bar" |bla/
"foo" "bar" "bla"/foo|bar|bla/"foo" |"bar" |"bla"/
"foo" bar "bla"/foo|bar|bla/"foo" |bar |"bla"/
"foo" bar bla/foo|bar|bla/"foo" |bar |bla/
foo 'bar' bla/foo|bar|bla/foo |'bar' |bla/
'foo' 'bar' 'bla'/foo|bar|bla/'foo' |'bar' |'bla'/
'foo' bar 'bla'/foo|bar|bla/'foo' |bar |'bla'/
'foo' bar bla/foo|bar|bla/'foo' |bar |bla/
blurb foo"bar"bar"fasel" baz/blurb|foobarbarfasel|baz/blurb |foo"bar"bar"fasel" |baz/
blurb foo'bar'bar'fasel' baz/blurb|foobarbarfasel|baz/blurb |foo'bar'bar'fasel' |baz/
""//""/
''//''/
foo "" bar/foo||bar/foo |"" |bar/
foo '' bar/foo||bar/foo |'' |bar/
foo "" "" "" bar/foo||||bar/foo |"" |"" |"" |bar/
foo '' '' '' bar/foo||||bar/foo |'' |'' |'' |bar/
\"/"/\"/
"\""/"/"\""/
"foo\ bar"/foo\ bar/"foo\ bar"/
"foo\\ bar"/foo\ bar/"foo\\ bar"/
"foo\\ bar\""/foo\ bar"/"foo\\ bar\""/
"foo\\" bar\"/foo\|bar"/"foo\\" |bar\"/
"foo\\ bar\" dfadf"/foo\ bar" dfadf/"foo\\ bar\" dfadf"/
"foo\\\ bar\" dfadf"/foo\\ bar" dfadf/"foo\\\ bar\" dfadf"/
"foo\\\x bar\" dfadf"/foo\\x bar" dfadf/"foo\\\x bar\" dfadf"/
"foo\x bar\" dfadf"/foo\x bar" dfadf/"foo\x bar\" dfadf"/
\'/'/\'/
'foo\ bar'/foo\ bar/'foo\ bar'/
'foo\\ bar'/foo\\ bar/'foo\\ bar'/
"foo\\\x bar\" df'a\ 'df"/foo\\x bar" df'a\ 'df/"foo\\\x bar\" df'a\ 'df"/
\"foo/"foo/\"foo/
\"foo\x/"foox/\"foo\x/
"foo\x"/foo\x/"foo\x"/
"foo\ "/foo\ /"foo\ "/
foo\ xx/foo xx/foo\ xx/
foo\ x\x/foo xx/foo\ x\x/
foo\ x\x\"/foo xx"/foo\ x\x\"/
"foo\ x\x"/foo\ x\x/"foo\ x\x"/
"foo\ x\x\\"/foo\ x\x\/"foo\ x\x\\"/
"foo\ x\x\\""foobar"/foo\ x\x\foobar/"foo\ x\x\\""foobar"/
"foo\ x\x\\"\'"foobar"/foo\ x\x\'foobar/"foo\ x\x\\"\'"foobar"/
"foo\ x\x\\"\'"fo'obar"/foo\ x\x\'fo'obar/"foo\ x\x\\"\'"fo'obar"/
"foo\ x\x\\"\'"fo'obar" 'don'\''t'/foo\ x\x\'fo'obar|don't/"foo\ x\x\\"\'"fo'obar" 'don'\''t'/
"foo\ x\x\\"\'"fo'obar" 'don'\''t' \\/foo\ x\x\'fo'obar|don't|\/"foo\ x\x\\"\'"fo'obar" |'don'\''t' |\\/
'foo\ bar'/foo\ bar/'foo\ bar'/
'foo\\ bar'/foo\\ bar/'foo\\ bar'/
foo\ bar/foo bar/foo\ bar/
foo#bar\nbaz/foo#bar|baz/foo#bar\n|baz/
:-) ;-)/:-)|;-)/:-) |;-)/
áéíóú/áéíóú/áéíóú/
"""

class SplitTests(unittest.TestCase):

    """Test split."""

    def test_split(self):
        """Test splitting."""
        for case in test_data.strip().splitlines():
            cmd, *out = case.split('/')[:-1]
            cmd = cmd.replace(r'\n', '\n')
            with self.subTest(cmd=cmd):
                items = split.split(cmd)
                self.assertEqual(items, out[0].split('|'))

    def test_split_keep_original(self):
        """Test if splitting with keep=True yields the original string."""
        for case in test_data.strip().splitlines():
            cmd, *_out = case.split('/')[:-1]
            cmd = cmd.replace(r'\n', '\n')
            with self.subTest(cmd=cmd):
                items = split.split(cmd, keep=True)
                self.assertEqual(''.join(items), cmd)

    def test_split_keep(self):
        """Test splitting with keep=True."""
        for case in test_data.strip().splitlines():
            cmd, *out = case.split('/')[:-1]
            cmd = cmd.replace(r'\n', '\n')
            with self.subTest(cmd=cmd):
                items = split.split(cmd, keep=True)
                self.assertEqual(items, out[1].split('|'))
