# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015 Daniel Schadt
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

"""pdf.js integration for qutebrowser."""

import os

from PyQt5.QtCore import QUrl, QUrlQuery

from qutebrowser.utils import (utils, javascript, jinja, qtutils, usertypes,
                               standarddir, log)
from qutebrowser.misc import objects
from qutebrowser.config import config


class PDFJSNotFound(Exception):

    """Raised when no pdf.js installation is found.

    Attributes:
        path: path of the file that was requested but not found.
    """

    def __init__(self, path):
        self.path = path
        message = "Path '{}' not found".format(path)
        super().__init__(message)


def generate_pdfjs_page(filename, url):
    """Return the html content of a page that displays a file with pdfjs.

    Returns a string.

    Args:
        filename: The filename of the PDF to open.
        url: The URL being opened.
    """
    if not is_available():
        pdfjs_dir = os.path.join(standarddir.data(), 'pdfjs')
        return jinja.render('no_pdfjs.html',
                            url=url.toDisplayString(),
                            title="PDF.js not found",
                            pdfjs_dir=pdfjs_dir)
    html = get_pdfjs_res('web/viewer.html').decode('utf-8')

    script = _generate_pdfjs_script(filename)
    html = html.replace('</body>',
                        '</body><script>{}</script>'.format(script))
    # WORKAROUND for the fact that PDF.js tries to use the Fetch API even with
    # qute:// URLs.
    pdfjs_script = '<script src="../build/pdf.js"></script>'
    html = html.replace(pdfjs_script,
                        '<script>window.Response = undefined;</script>\n' +
                        pdfjs_script)
    return html


def _generate_pdfjs_script(filename):
    """Generate the script that shows the pdf with pdf.js.

    Args:
        filename: The name of the file to open.
    """
    url = QUrl('qute://pdfjs/file')
    url_query = QUrlQuery()
    url_query.addQueryItem('filename', filename)
    url.setQuery(url_query)

    js_url = javascript.to_js(
        url.toString(QUrl.FullyEncoded))  # type: ignore[arg-type]

    return jinja.js_environment.from_string("""
        document.addEventListener("DOMContentLoaded", function() {
          if (typeof window.PDFJS !== 'undefined') {
              // v1.x
              {% if disable_create_object_url %}
              window.PDFJS.disableCreateObjectURL = true;
              {% endif %}
              window.PDFJS.verbosity = window.PDFJS.VERBOSITY_LEVELS.info;
          } else {
              // v2.x
              const options = window.PDFViewerApplicationOptions;
              {% if disable_create_object_url %}
              options.set('disableCreateObjectURL', true);
              {% endif %}
              options.set('verbosity', pdfjsLib.VerbosityLevel.INFOS);
          }

          const viewer = window.PDFView || window.PDFViewerApplication;
          viewer.open({{ url }});
        });
    """).render(
        url=js_url,
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-70420
        disable_create_object_url=(
            not qtutils.version_check('5.12') and
            not qtutils.version_check('5.7.1', exact=True, compiled=False) and
            objects.backend == usertypes.Backend.QtWebEngine))


def get_pdfjs_res_and_path(path):
    """Get a pdf.js resource in binary format.

    Returns a (content, path) tuple, where content is the file content and path
    is the path where the file was found. If path is None, the bundled version
    was used.

    Args:
        path: The path inside the pdfjs directory.
    """
    path = path.lstrip('/')
    content = None
    file_path = None

    system_paths = [
        # Debian pdf.js-common
        # Arch Linux pdfjs (AUR)
        '/usr/share/pdf.js/',
        # Flatpak (Flathub)
        '/app/share/pdf.js/',
        # Arch Linux pdf.js (AUR)
        '/usr/share/javascript/pdf.js/',
        # Debian libjs-pdf
        '/usr/share/javascript/pdf/',
        # fallback
        os.path.join(standarddir.data(), 'pdfjs'),
        # hardcoded fallback for --temp-basedir
        os.path.expanduser('~/.local/share/qutebrowser/pdfjs/'),
    ]

    # First try a system wide installation
    # System installations might strip off the 'build/' or 'web/' prefixes.
    # qute expects them, so we need to adjust for it.
    names_to_try = [path, _remove_prefix(path)]
    for system_path in system_paths:
        content, file_path = _read_from_system(system_path, names_to_try)
        if content is not None:
            break

    # Fallback to bundled pdf.js
    if content is None:
        res_path = '3rdparty/pdfjs/{}'.format(path)
        try:
            content = utils.read_file(res_path, binary=True)
        except FileNotFoundError:
            raise PDFJSNotFound(path) from None
        except OSError as e:
            log.misc.warning("OSError while reading PDF.js file: {}".format(e))
            raise PDFJSNotFound(path) from None

    return content, file_path


def get_pdfjs_res(path):
    """Get a pdf.js resource in binary format.

    Args:
        path: The path inside the pdfjs directory.
    """
    content, _path = get_pdfjs_res_and_path(path)
    return content


def _remove_prefix(path):
    """Remove the web/ or build/ prefix of a pdfjs-file-path.

    Args:
        path: Path as string where the prefix should be stripped off.
    """
    prefixes = {'web/', 'build/'}
    if any(path.startswith(prefix) for prefix in prefixes):
        return path.split('/', maxsplit=1)[1]
    # Return the unchanged path if no prefix is found
    return path


def _read_from_system(system_path, names):
    """Try to read a file with one of the given names in system_path.

    Returns a (content, path) tuple, where the path is the filepath that was
    used.

    Each file in names is considered equal, the first file that is found
    is read and its binary content returned.

    Returns (None, None) if no file could be found

    Args:
        system_path: The folder where the file should be searched.
        names: List of possible file names.
    """
    for name in names:
        try:
            full_path = os.path.join(system_path, name)
            with open(full_path, 'rb') as f:
                return (f.read(), full_path)
        except FileNotFoundError:
            continue
        except OSError as e:
            log.misc.warning("OSError while reading PDF.js file: {}".format(e))
            continue
    return (None, None)


def is_available():
    """Return true if a pdfjs installation is available."""
    try:
        get_pdfjs_res('build/pdf.js')
    except PDFJSNotFound:
        return False
    else:
        return True


def should_use_pdfjs(mimetype, url):
    """Check whether PDF.js should be used."""
    # e.g. 'blob:qute%3A///b45250b3-787e-44d1-a8d8-c2c90f81f981'
    is_download_url = (url.scheme() == 'blob' and
                       QUrl(url.path()).scheme() == 'qute')
    is_pdf = mimetype in ['application/pdf', 'application/x-pdf']
    config_enabled = config.instance.get('content.pdfjs', url=url)
    return is_pdf and not is_download_url and config_enabled


def get_main_url(filename: str, original_url: QUrl) -> QUrl:
    """Get the URL to be opened to view a local PDF."""
    url = QUrl('qute://pdfjs/web/viewer.html')
    query = QUrlQuery()
    query.addQueryItem('filename', filename)  # read from our JS
    query.addQueryItem('file', '')  # to avoid pdfjs opening the default PDF
    urlstr = original_url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]
    query.addQueryItem('source', urlstr)
    url.setQuery(query)
    return url
