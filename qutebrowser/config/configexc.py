# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
        section: Section in which the error occurred (added when catching and
                 re-raising the exception).
        option: Option in which the error occurred.
    """

    def __init__(self, value, msg):
        super().__init__("Invalid value '{}' - {}".format(value, msg))
        self.section = None
        self.option = None


class NoSectionError(Error):

    """Raised when no section matches a requested option."""

    def __init__(self, section):
        super().__init__("Section {!r} does not exist!".format(section))
        self.section = section


class NoOptionError(Error):

    """Raised when an option was not found."""

    def __init__(self, option, section):
        super().__init__("No option {!r} in section {!r}".format(
            option, section))
        self.option = option
        self.section = section


class InterpolationSyntaxError(Error):

    """Raised when the source text contains invalid syntax.

    Current implementation raises this exception when the source text into
    which substitutions are made does not conform to the required syntax.
    """

    def __init__(self, option, section, msg):
        super().__init__(msg)
        self.option = option
        self.section = section
