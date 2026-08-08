from typing import cast

from qutebrowser.config.configcontainer_types import ConfigContainer  # pylint: disable=unused-import
from qutebrowser.config import configfiles  # pylint: disable=unused-import


c = cast('ConfigContainer', None)
config = cast('configfiles.ConfigAPI', None)
