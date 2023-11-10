# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Functions dealing with user-defined exceptions."""


class DeserializationError(Exception):
    """Exception that is realized whenever a file fails to deserialize."""
