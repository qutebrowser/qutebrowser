# SPDX-FileCopyrightText: Daniel Schadt
# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""pdf.js integration for qutebrowser."""

import os

from qutebrowser.qt.core import QUrl, QUrlQuery

from qutebrowser.utils import resources, javascript, jinja, standarddir, log, urlutils
from qutebrowser.config import config
from qutebrowser.misc import objects


_SYSTEM_PATHS = [
    # Debian pdf.js-common
    # Arch Linux pdfjs
    '/usr/share/pdf.js/',
    # Flatpak (Flathub)
    '/app/share/pdf.js/',
    # Arch Linux pdf.js (defunct)
    '/usr/share/javascript/pdf.js/',
    # Debian libjs-pdf
    '/usr/share/javascript/pdf/',
]


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
    # qute:// URLs, this is probably no longer needed in PDFjs 4+. See #4235
    html = html.replace(
        '<head>',
        '<head>\n<script>window.Response = undefined;</script>\n'
    )
    return html


def _get_polyfills() -> str:
    return resources.read_file("javascript/pdfjs_polyfills.js")


def _generate_pdfjs_script(filename):
    """Generate the script that shows the pdf with pdf.js.

    Args:
        filename: The name of the file to open.
    """
    url = QUrl('qute://pdfjs/file')
    url_query = QUrlQuery()
    url_query.addQueryItem('filename', filename)
    url.setQuery(url_query)

    js_url = javascript.to_js(url.toString(urlutils.FormatOption.ENCODED))

    return jinja.js_environment.from_string("""
        {{ polyfills }}

        document.addEventListener("DOMContentLoaded", function() {
            if (typeof window.PDFJS !== 'undefined') {
                // v1.x
                window.PDFJS.verbosity = window.PDFJS.VERBOSITY_LEVELS.info;
            } else {
                // v2.x+
                const options = window.PDFViewerApplicationOptions;
                options.set('verbosity', pdfjsLib.VerbosityLevel.INFOS);
            }

            if (typeof window.PDFView !== 'undefined') {
                // < v1.6
                window.PDFView.open({{ url }});
            } else {
                // v1.6+
                window.PDFViewerApplication.open({
                    url: {{ url }},
                    originalUrl: {{ url }}
                });
            }
        });
    """).render(url=js_url, polyfills=_get_polyfills())


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

    if 'no-system-pdfjs' in objects.debug_flags:
        system_paths = []
    else:
        system_paths = _SYSTEM_PATHS[:]

    system_paths += [
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
            content = resources.read_file_binary(res_path)
        except FileNotFoundError:
            raise PDFJSNotFound(path) from None
        except OSError as e:
            log.misc.warning("OSError while reading PDF.js file: {}".format(e))
            raise PDFJSNotFound(path) from None

    if path == "build/pdf.worker.mjs":
        content = b"\n".join(
            [
                _get_polyfills().encode("ascii"),
                content,
            ]
        )

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


def get_pdfjs_js_path():
    """Checks for pdf.js main module availability and returns the path if available."""
    paths = ['build/pdf.js', 'build/pdf.mjs']
    for path in paths:
        try:
            get_pdfjs_res(path)
        except PDFJSNotFound:
            pass
        else:
            return path

    raise PDFJSNotFound(" or ".join(paths))


def is_available():
    """Return true if certain parts of a pdfjs installation are available."""
    try:
        get_pdfjs_js_path()
        get_pdfjs_res('web/viewer.html')
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
    urlstr = original_url.toString(urlutils.FormatOption.ENCODED)
    query.addQueryItem('source', urlstr)
    url.setQuery(query)
    return url
