# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""pytest fixtures and utilities for testing.

Fixtures defined here will be visible to all test files in this directory and
below.
"""

import pytest

from qutebrowser.config.config import ConfigManager
from qutebrowser.utils import objreg


@pytest.yield_fixture
def default_config():
    """
    Fixture that registers an empty config object into the objreg module.

    Should be used by tests which create widgets that obtain their initial
    state from the global config object.

    Note:

        If we declare this fixture like this:

            @pytest.yield_fixture(autouse=True)

        Then all tests below this file will have a default config registered
        and ready for use. Is that desirable?
    """
    config_obj = ConfigManager(configdir=None, fname=None, relaxed=True)
    objreg.register('config', config_obj)
    yield config_obj
    objreg.delete('config')
