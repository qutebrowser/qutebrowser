# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
