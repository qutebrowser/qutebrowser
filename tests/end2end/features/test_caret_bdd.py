# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest_bdd as bdd

# pylint: disable=unused-import
from end2end.features.test_yankpaste_bdd import init_fake_clipboard

bdd.scenarios('caret.feature')
