# SPDX-FileCopyrightText: Jay Kamat <jaygkamat@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Implementation of a basic config cache."""

from typing import Any

from qutebrowser.config import config


class ConfigCache:

    """A 'high-performance' cache for the config system.

    Useful for areas which call out to the config system very frequently, DO
    NOT modify the value returned, DO NOT require per-url settings, and do not
    require partially 'expanded' config paths.

    If any of these requirements are broken, you will get incorrect or slow
    behavior.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        config.instance.changed.connect(self._on_config_changed)

    def _on_config_changed(self, attr: str) -> None:
        if attr in self._cache:
            del self._cache[attr]

    def __getitem__(self, attr: str) -> Any:
        try:
            return self._cache[attr]
        except KeyError:
            assert not config.instance.get_opt(attr).supports_pattern
            result = self._cache[attr] = config.instance.get(attr)
            return result
