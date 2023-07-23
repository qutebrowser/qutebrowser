# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test qutebrowser.misc.earlyinit."""

import sys

import pytest

from qutebrowser.misc import earlyinit


@pytest.mark.parametrize('attr', ['stderr', '__stderr__'])
def test_init_faulthandler_stderr_none(monkeypatch, attr):
    """Make sure init_faulthandler works when sys.stderr/__stderr__ is None."""
    monkeypatch.setattr(sys, attr, None)
    earlyinit.init_faulthandler()


@pytest.mark.parametrize('same', [True, False])
def test_qt_version(same):
    if same:
        qt_version_str = '5.14.0'
        expected = '5.14.0'
    else:
        qt_version_str = '5.13.0'
        expected = '5.14.0 (compiled 5.13.0)'
    actual = earlyinit.qt_version(qversion='5.14.0', qt_version_str=qt_version_str)
    assert actual == expected


def test_qt_version_no_args():
    """Make sure qt_version without arguments at least works."""
    earlyinit.qt_version()
