# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Various meta-tests for conftest.py."""


import os
import sys
import warnings

import pytest

import qutebrowser


def test_qapp_name(qapp):
    """Make sure the QApplication name is changed when we use qapp."""
    assert qapp.applicationName() == 'qute_test'


def test_no_qapp(request):
    """Make sure a test without qapp doesn't use qapp (via autouse)."""
    assert 'qapp' not in request.fixturenames


def test_fail_on_warnings():
    with pytest.raises(PendingDeprecationWarning):
        warnings.warn('test', PendingDeprecationWarning)


@pytest.mark.xfail(reason="https://github.com/qutebrowser/qutebrowser/issues/1070",
                   strict=False)
def test_installed_package():
    """Make sure the tests are running against the installed package."""
    print(sys.path)
    assert '.tox' in qutebrowser.__file__.split(os.sep)
