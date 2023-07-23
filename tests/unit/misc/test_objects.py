# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.misc import objects
from qutebrowser.utils import usertypes


@pytest.mark.parametrize('func', [
    lambda: objects.NoBackend() == usertypes.Backend.QtWebEngine,
    lambda: objects.NoBackend() != usertypes.Backend.QtWebEngine,
    lambda: objects.NoBackend() in [usertypes.Backend.QtWebEngine],
])
def test_no_backend(func):
    with pytest.raises(AssertionError, match='No backend set!'):
        func()
