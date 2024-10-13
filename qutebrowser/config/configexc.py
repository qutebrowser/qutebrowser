# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exceptions related to config parsing."""

import difflib
import dataclasses
from typing import Any, Optional, Union
from collections.abc import Mapping, Sequence

from qutebrowser.utils import usertypes, log


class Error(Exception):

    """Base exception for config-related errors."""


class NoAutoconfigError(Error):

    """Raised when this option can't be set in autoconfig.yml."""

    def __init__(self, name: str) -> None:
        super().__init__("The {} setting can only be set in config.py!"
                         .format(name))


class BackendError(Error):

    """Raised when this setting is unavailable with the current backend."""

    def __init__(
            self, name: str,
            backend: usertypes.Backend,
            raw_backends: Optional[Mapping[str, bool]]
    ) -> None:
        if raw_backends is None or not raw_backends[backend.name]:
            msg = ("The {} setting is not available with the {} backend!"
                   .format(name, backend.name))
        else:
            msg = ("The {} setting needs {} with the {} backend!"
                   .format(name, raw_backends[backend.name], backend.name))

        super().__init__(msg)


class NoPatternError(Error):

    """Raised when the given setting does not support URL patterns."""

    def __init__(self, name: str) -> None:
        super().__init__("The {} setting does not support URL patterns!"
                         .format(name))


class ValidationError(Error):

    """Raised when a value for a config type was invalid.

    Attributes:
        value: Config value that triggered the error.
        msg: Additional error message.
    """

    def __init__(self, value: Any, msg: Union[str, Exception]) -> None:
        super().__init__("Invalid value '{}' - {}".format(value, msg))
        self.option = None


class KeybindingError(Error):

    """Raised for issues with keybindings."""


class NoOptionError(Error):

    """Raised when an option was not found."""

    def __init__(self, option: str, *,
                 all_names: list[str] = None,
                 deleted: bool = False,
                 renamed: str = None) -> None:
        if deleted:
            assert renamed is None
            suffix = ' (this option was removed from qutebrowser)'
        elif renamed is not None:
            suffix = ' (this option was renamed to {!r})'.format(renamed)
        elif all_names:
            matches = difflib.get_close_matches(option, all_names, n=1)
            if matches:
                suffix = f' (did you mean {matches[0]!r}?)'
            else:
                suffix = ''
        else:
            suffix = ''

        super().__init__("No option {!r}{}".format(option, suffix))
        self.option = option


@dataclasses.dataclass
class ConfigErrorDesc:

    """A description of an error happening while reading the config.

    Attributes:
        text: The text to show.
        exception: The exception which happened.
        traceback: The formatted traceback of the exception.
    """

    text: str
    exception: Union[str, Exception]
    traceback: Optional[str] = None

    def __str__(self) -> str:
        if self.traceback:
            return '{} - {}: {}'.format(self.text,
                                        self.exception.__class__.__name__,
                                        self.exception)
        return '{}: {}'.format(self.text, self.exception)

    def with_text(self, text: str) -> 'ConfigErrorDesc':
        """Get a new ConfigErrorDesc with the given text appended."""
        return self.__class__(text='{} ({})'.format(self.text, text),
                              exception=self.exception,
                              traceback=self.traceback)


class ConfigFileErrors(Error):

    """Raised when multiple errors occurred inside the config."""

    def __init__(self,
                 basename: str,
                 errors: Sequence[ConfigErrorDesc], *,
                 fatal: bool = False) -> None:
        super().__init__("Errors occurred while reading {}:\n{}".format(
            basename, '\n'.join('  {}'.format(e) for e in errors)))
        self.basename = basename
        self.errors = errors
        self.fatal = fatal
        for err in errors:
            if err.traceback:
                log.config.info(err.traceback)

    def to_html(self) -> str:
        """Get the error texts as a HTML snippet."""
        from qutebrowser.utils import jinja  # circular import
        template = jinja.environment.from_string("""
        Errors occurred while reading {{ basename }}:

        <ul>
          {% for error in errors %}
            <li>
              <b>{{ error.text }}</b>: {{ error.exception }}
              {% if error.traceback != none %}
                <pre>
        """.rstrip() + "\n{{ error.traceback }}" + """
                </pre>
              {% endif %}
            </li>
          {% endfor %}
        </ul>
        """)
        return template.render(basename=self.basename, errors=self.errors)
