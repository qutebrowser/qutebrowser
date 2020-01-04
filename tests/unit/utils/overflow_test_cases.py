# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Provides test data for overflow checking.

Module attributes:
    INT32_MIN: Minimum valid value for a signed int32.
    INT32_MAX: Maximum valid value for a signed int32.
    INT64_MIN: Minimum valid value for a signed int64.
    INT64_MAX: Maximum valid value for a signed int64.
    GOOD_VALUES: A dict of types mapped to a list of good values.
    BAD_VALUES: A dict of types mapped to a list of bad values.
"""

INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1
INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1

GOOD_VALUES = {
    'int': [-1, 0, 1, 23.42, INT32_MIN, INT32_MAX],
    'int64': [-1, 0, 1, 23.42, INT64_MIN, INT64_MAX],
}

BAD_VALUES = {
    'int': [(INT32_MIN - 1, INT32_MIN),
            (INT32_MAX + 1, INT32_MAX),
            (float(INT32_MAX + 1), INT32_MAX)],
    'int64': [(INT64_MIN - 1, INT64_MIN),
              (INT64_MAX + 1, INT64_MAX),
              (float(INT64_MAX + 1), INT64_MAX)],
}


def good_values():
    return list(iter_good_values())


def bad_values():
    return list(iter_bad_values())


def iter_good_values():
    """Yield "good" (C data type, value) tuples.

    Those should pass overflow checking.
    """
    for ctype, values in sorted(GOOD_VALUES.items()):
        for value in values:
            yield ctype, value


def iter_bad_values():
    """Yield pairs of "bad" (C type, value, repl) tuples.

    These should not pass overflow checking. The third value is the value they
    should be replaced with if overflow checking should not be fatal.
    """
    for ctype, values in sorted(BAD_VALUES.items()):
        for value, repl in values:
            yield ctype, value, repl
