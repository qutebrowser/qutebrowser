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


import fnmatch


def _partial_compare_dict(val1, val2):
    for key in val2:
        if key not in val1:
            print("Key {!r} is in second dict but not in first!".format(key))
            return False
        if not partial_compare(val1[key], val2[key]):
            print("Comparison failed for {!r} and {!r}!".format(
                val1[key], val2[key]))
            return False
    return True


def _partial_compare_list(val1, val2):
    if len(val1) < len(val2):
        print("Second list is longer than first list -> False!")
        return False
    for item1, item2 in zip(val1, val2):
        if not partial_compare(item1, item2):
            return False
    return True


def partial_compare(val1, val2):
    """Do a partial comparison between the given values.

    For dicts, keys in val2 are checked, others are ignored.
    For lists, entries at the positions in val2 are checked, others ignored.
    For other values, == is used.

    This happens recursively.
    """
    print()
    print("Comparing\n    {!r}\nto\n    {!r}".format(val1, val2))

    if val2 is Ellipsis:
        print("Ignoring ellipsis comparison")
        return True
    elif type(val1) != type(val2):  # pylint: disable=unidiomatic-typecheck
        print("Different types ({}, {}) -> False".format(
            type(val1), type(val2)))
        return False

    if isinstance(val2, dict):
        print("Comparing as dicts")
        equal = _partial_compare_dict(val1, val2)
    elif isinstance(val2, list):
        print("Comparing as lists")
        equal = _partial_compare_list(val1, val2)
    elif isinstance(val2, float):
        print("Doing float comparison")
        equal = abs(val1 - val2) < 0.00001
    elif isinstance(val2, str):
        print("Doing string comparison")
        equal = fnmatch.fnmatchcase(val1, val2)
    else:
        print("Comparing via ==")
        equal = val1 == val2
    print("---> {}".format(equal))
    return equal
