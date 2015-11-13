# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Partial comparison of dicts/lists."""


import re
import pprint


def print_i(text, indent, error=False):
    if error:
        text = '| ****** {} ******'.format(text)
    for line in text.splitlines():
        print('|   ' * indent + line)


def _partial_compare_dict(val1, val2, *, indent=0):
    for key in val2:
        if key not in val1:
            print_i("Key {!r} is in second dict but not in first!".format(key),
                    indent, error=True)
            return False
        if not partial_compare(val1[key], val2[key], indent=indent+1):
            return False
    return True


def _partial_compare_list(val1, val2, *, indent=0):
    if len(val1) < len(val2):
        print_i("Second list is longer than first list", indent, error=True)
        return False
    for item1, item2 in zip(val1, val2):
        if not partial_compare(item1, item2, indent=indent+1):
            return False
    return True


def partial_compare(val1, val2, *, indent=0):
    """Do a partial comparison between the given values.

    For dicts, keys in val2 are checked, others are ignored.
    For lists, entries at the positions in val2 are checked, others ignored.
    For other values, == is used.

    This happens recursively.
    """
    print_i("Comparing", indent)
    print_i(pprint.pformat(val1), indent + 1)
    print_i("|---- to ----", indent)
    print_i(pprint.pformat(val2), indent + 1)


    if val2 is Ellipsis:
        print_i("Ignoring ellipsis comparison", indent, error=True)
        return True
    elif type(val1) != type(val2):  # pylint: disable=unidiomatic-typecheck
        print_i("Different types ({}, {}) -> False".format(
                type(val1), type(val2)), indent, error=True)
        return False

    if isinstance(val2, dict):
        print_i("|======= Comparing as dicts", indent)
        equal = _partial_compare_dict(val1, val2, indent=indent)
    elif isinstance(val2, list):
        print_i("|======= Comparing as lists", indent)
        equal = _partial_compare_list(val1, val2, indent=indent)
    elif isinstance(val2, float):
        print_i("|======= Doing float comparison", indent)
        equal = abs(val1 - val2) < 0.00001
    elif isinstance(val2, str):
        print_i("|======= Doing string comparison", indent)
        equal = pattern_match(pattern=val2, value=val1)
    else:
        print_i("|======= Comparing via ==", indent)
        equal = val1 == val2
    print_i("---> {}".format(equal), indent)
    return equal


def pattern_match(*, pattern, value):
    """Do fnmatch.fnmatchcase like matching, but only with * active.

    Return:
        True on a match, False otherwise.
    """
    re_pattern = '.*'.join(re.escape(part) for part in pattern.split('*'))
    return re.fullmatch(re_pattern, value) is not None
