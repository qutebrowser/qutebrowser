"""
pytest fixtures and utilities for testing.

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

    Should be used by tests which create widgets that obtain their initial state
    from the global config object.

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