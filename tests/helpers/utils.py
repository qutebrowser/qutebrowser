# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various utilities used inside tests."""

import io
import re
import gzip
import pprint
import os.path
import contextlib

import pytest

from qutebrowser.utils import qtutils, log

ON_CI = 'CI' in os.environ

qt58 = pytest.mark.skipif(
    qtutils.version_check('5.9'), reason="Needs Qt 5.8 or earlier")
qt59 = pytest.mark.skipif(
    not qtutils.version_check('5.9'), reason="Needs Qt 5.9 or newer")
qt510 = pytest.mark.skipif(
    not qtutils.version_check('5.10'), reason="Needs Qt 5.10 or newer")
qt514 = pytest.mark.skipif(
    not qtutils.version_check('5.14'), reason="Needs Qt 5.14 or newer")
skip_qt511 = pytest.mark.skipif(
    qtutils.version_check('5.11'), reason="Needs Qt 5.10 or earlier")


class PartialCompareOutcome:

    """Storage for a partial_compare error.

    Evaluates to False if an error was found.

    Attributes:
        error: A string describing an error or None.
    """

    def __init__(self, error=None):
        self.error = error

    def __bool__(self):
        return self.error is None

    def __repr__(self):
        return 'PartialCompareOutcome(error={!r})'.format(self.error)

    def __str__(self):
        return 'true' if self.error is None else 'false'


def print_i(text, indent, error=False):
    if error:
        text = '| ****** {} ******'.format(text)
    for line in text.splitlines():
        print('|   ' * indent + line)


def _partial_compare_dict(val1, val2, *, indent):
    for key in val2:
        if key not in val1:
            outcome = PartialCompareOutcome(
                "Key {!r} is in second dict but not in first!".format(key))
            print_i(outcome.error, indent, error=True)
            return outcome
        outcome = partial_compare(val1[key], val2[key], indent=indent + 1)
        if not outcome:
            return outcome
    return PartialCompareOutcome()


def _partial_compare_list(val1, val2, *, indent):
    if len(val1) < len(val2):
        outcome = PartialCompareOutcome(
            "Second list is longer than first list")
        print_i(outcome.error, indent, error=True)
        return outcome
    for item1, item2 in zip(val1, val2):
        outcome = partial_compare(item1, item2, indent=indent + 1)
        if not outcome:
            return outcome
    return PartialCompareOutcome()


def _partial_compare_float(val1, val2, *, indent):
    if val1 == pytest.approx(val2):
        return PartialCompareOutcome()

    return PartialCompareOutcome("{!r} != {!r} (float comparison)".format(
        val1, val2))


def _partial_compare_str(val1, val2, *, indent):
    if pattern_match(pattern=val2, value=val1):
        return PartialCompareOutcome()

    return PartialCompareOutcome("{!r} != {!r} (pattern matching)".format(
        val1, val2))


def _partial_compare_eq(val1, val2, *, indent):
    if val1 == val2:
        return PartialCompareOutcome()
    return PartialCompareOutcome("{!r} != {!r}".format(val1, val2))


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
        return PartialCompareOutcome()
    elif type(val1) != type(val2):  # pylint: disable=unidiomatic-typecheck
        outcome = PartialCompareOutcome(
            "Different types ({}, {}) -> False".format(type(val1).__name__,
                                                       type(val2).__name__))
        print_i(outcome.error, indent, error=True)
        return outcome

    handlers = {
        dict: _partial_compare_dict,
        list: _partial_compare_list,
        float: _partial_compare_float,
        str: _partial_compare_str,
    }

    for typ, handler in handlers.items():
        if isinstance(val2, typ):
            print_i("|======= Comparing as {}".format(typ.__name__), indent)
            outcome = handler(val1, val2, indent=indent)
            break
    else:
        print_i("|======= Comparing via ==", indent)
        outcome = _partial_compare_eq(val1, val2, indent=indent)
    print_i("---> {}".format(outcome), indent)
    return outcome


def pattern_match(*, pattern, value):
    """Do fnmatch.fnmatchcase like matching, but only with * active.

    Return:
        True on a match, False otherwise.
    """
    re_pattern = '.*'.join(re.escape(part) for part in pattern.split('*'))
    return re.fullmatch(re_pattern, value, flags=re.DOTALL) is not None


def abs_datapath():
    """Get the absolute path to the end2end data directory."""
    file_abs = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(file_abs, '..', 'end2end', 'data')


@contextlib.contextmanager
def nop_contextmanager():
    yield


@contextlib.contextmanager
def ignore_bs4_warning():
    """WORKAROUND for https://bugs.launchpad.net/beautifulsoup/+bug/1847592."""
    with log.ignore_py_warnings(
            category=DeprecationWarning,
            message="Using or importing the ABCs from 'collections' instead "
            "of from 'collections.abc' is deprecated", module='bs4.element'):
        yield


def blocked_hosts():
    path = os.path.join(abs_datapath(), 'blocked-hosts.gz')
    yield from io.TextIOWrapper(gzip.open(path), encoding='utf-8')
