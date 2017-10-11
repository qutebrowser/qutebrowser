# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Exceptions related to config parsing."""

import attr

from qutebrowser.utils import jinja


class Error(Exception):

    """Base exception for config-related errors."""

    pass


class BackendError(Error):

    """Raised when this setting is unavailable with the current backend."""

    def __init__(self, backend):
        super().__init__("This setting is not available with the {} "
                         "backend!".format(backend.name))


class ValidationError(Error):

    """Raised when a value for a config type was invalid.

    Attributes:
        value: Config value that triggered the error.
        msg: Additional error message.
    """

    def __init__(self, value, msg):
        super().__init__("Invalid value '{}' - {}".format(value, msg))
        self.option = None


class KeybindingError(Error):

    """Raised for issues with keybindings."""


class NoOptionError(Error):

    """Raised when an option was not found."""

    def __init__(self, option, *, deleted=False, renamed=None):
        if deleted:
            assert renamed is None
            suffix = ' (this option was removed from qutebrowser)'
        elif renamed is not None:
            suffix = ' (this option was renamed to {!r})'.format(renamed)
        else:
            suffix = ''

        super().__init__("No option {!r}{}".format(option, suffix))
        self.option = option


@attr.s
class ConfigErrorDesc:

    """A description of an error happening while reading the config.

    Attributes:
        text: The text to show.
        exception: The exception which happened.
        traceback: The formatted traceback of the exception.
    """

    text = attr.ib()
    exception = attr.ib()
    traceback = attr.ib(None)

    def __str__(self):
        return '{}: {}'.format(self.text, self.exception)

    def with_text(self, text):
        """Get a new ConfigErrorDesc with the given text appended."""
        return self.__class__(text='{} ({})'.format(self.text, text),
                              exception=self.exception,
                              traceback=self.traceback)


class ConfigFileErrors(Error):

    """Raised when multiple errors occurred inside the config."""

    def __init__(self, basename, errors):
        super().__init__("Errors occurred while reading {}:\n{}".format(
            basename, '\n'.join('  {}'.format(e) for e in errors)))
        self.basename = basename
        self.errors = errors

    def to_html(self):
        """Get the error texts as a HTML snippet."""
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
