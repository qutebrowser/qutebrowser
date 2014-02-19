# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Handler functions for different about:... pages."""

from qutebrowser.utils.version import version
from qutebrowser.utils.url import is_about_url


_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""


pyeval_output = None


def handle(url):
    """Handle about page with an url.

    Args:
        url: The url (string) to serve the about page for.

    Raise:
        ValueError if passed URL is not an about URL

    Return:
        HTML content as bytes.

    """
    if not is_about_url(url):
        raise ValueError
    handler = getattr(AboutHandlers, _transform_url(url))
    return handler()


def _transform_url(url):
    """Transform a special URL to an AboutHandlers method name.

    Args:
        url: The URL as string.

    Return:
        The method name about_*

    """
    return url.replace('http://', '').replace('about:', 'about_')


def _get_html(title, snippet):
    """Add HTML boilerplate to a html snippet.

    Args:
        title: The title the page should have.
        snippet: The html snippet.

    Return:
        HTML content as bytes.

    """
    return _HTML_TEMPLATE.format(title=title, body=snippet).encode('UTF-8')


class AboutHandlers:

    """Handlers for about:... pages."""

    @classmethod
    def about_pyeval(cls):
        """Handler for about:pyeval. Return HTML content as bytes."""
        return _get_html('pyeval', '<pre>{}</pre>'.format(pyeval_output))

    @classmethod
    def about_version(cls):
        """Handler for about:version. Return HTML content as bytes."""
        return _get_html('Version', '<pre>{}</pre>'.format(version()))
