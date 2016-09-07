# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various utilities shared between webpage/webview subclasses."""

from qutebrowser.config import config


def custom_headers():
    """Get the combined custom headers."""
    headers = {}
    dnt = b'1' if config.get('network', 'do-not-track') else b'0'
    headers[b'DNT'] = dnt
    headers[b'X-Do-Not-Track'] = dnt

    config_headers = config.get('network', 'custom-headers')
    if config_headers is not None:
        for header, value in config_headers.items():
            headers[header.encode('ascii')] = value.encode('ascii')

    accept_language = config.get('network', 'accept-language')
    if accept_language is not None:
        headers[b'Accept-Language'] = accept_language.encode('ascii')

    return sorted(headers.items())
