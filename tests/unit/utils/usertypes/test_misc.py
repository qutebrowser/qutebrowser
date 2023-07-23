# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from qutebrowser.utils import usertypes


def test_unset_object_identity():
    assert usertypes.Unset() is not usertypes.Unset()
    assert usertypes.UNSET is usertypes.UNSET


def test_unset_object_repr():
    assert repr(usertypes.UNSET) == '<UNSET>'
