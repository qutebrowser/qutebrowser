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

"""Implementation of :navigate."""

import posixpath

from qutebrowser.browser import webelem
from qutebrowser.config import config
from qutebrowser.utils import objreg, urlutils, log, message, qtutils


class Error(Exception):

    """Raised when the navigation can't be done."""


def incdec(url, count, inc_or_dec):
    """Helper method for :navigate when `where' is increment/decrement.

    Args:
        url: The current url.
        count: How much to increment or decrement by.
        inc_or_dec: Either 'increment' or 'decrement'.
        tab: Whether to open the link in a new tab.
        background: Open the link in a new background tab.
        window: Open the link in a new window.
    """
    segments = set(config.get('general', 'url-incdec-segments'))
    try:
        new_url = urlutils.incdec_number(url, inc_or_dec, count,
                                         segments=segments)
    except urlutils.IncDecError as error:
        raise Error(error.msg)
    return new_url


def path_up(url, count):
    """Helper method for :navigate when `where' is up.

    Args:
        url: The current url.
        count: The number of levels to go up in the url.
    """
    path = url.path()
    if not path or path == '/':
        raise Error("Can't go up!")
    for _i in range(0, min(count, path.count('/'))):
        path = posixpath.join(path, posixpath.pardir)
    url.setPath(path)
    return url


def _find_prevnext(prev, elems):
    """Find a prev/next element in the given list of elements."""
    # First check for <link rel="prev(ious)|next">
    rel_values = ('prev', 'previous') if prev else ('next')
    for e in elems:
        if e.tag_name() != 'link' or 'rel' not in e:
            continue
        if e['rel'] in rel_values:
            log.hints.debug("Found {!r} with rel={}".format(e, e['rel']))
            return e

    # Then check for regular links/buttons.
    filterfunc = webelem.FILTERS[webelem.Group.prevnext]
    elems = [e for e in elems if e.tag_name() != 'link' and filterfunc(e)]
    option = 'prev-regexes' if prev else 'next-regexes'
    if not elems:
        return None
    for regex in config.get('hints', option):
        log.hints.vdebug("== Checking regex '{}'.".format(regex.pattern))
        for e in elems:
            text = str(e)
            if not text:
                continue
            if regex.search(text):
                log.hints.debug("Regex '{}' matched on '{}'.".format(
                    regex.pattern, text))
                return e
            else:
                log.hints.vdebug("No match on '{}'!".format(text))
    return None


def prevnext(*, browsertab, win_id, baseurl, prev=False,
             tab=False, background=False, window=False):
    """Click a "previous"/"next" element on the page.

    Args:
        browsertab: The WebKitTab/WebEngineTab of the page.
        baseurl: The base URL of the current tab.
        prev: True to open a "previous" link, False to open a "next" link.
        tab: True to open in a new tab, False for the current tab.
        background: True to open in a background tab.
        window: True to open in a new window, False for the current one.
    """
    def _prevnext_cb(elems):
        if elems is None:
            message.error("There was an error while getting hint elements")
            return

        elem = _find_prevnext(prev, elems)
        word = 'prev' if prev else 'forward'

        if elem is None:
            message.error("No {} links found!".format(word))
            return
        url = elem.resolve_url(baseurl)
        if url is None:
            message.error("No {} links found!".format(word))
            return
        qtutils.ensure_valid(url)

        if window:
            from qutebrowser.mainwindow import mainwindow
            new_window = mainwindow.MainWindow()
            new_window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=new_window.win_id)
            tabbed_browser.tabopen(url, background=False)
        elif tab:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.tabopen(url, background=background)
        else:
            browsertab.openurl(url)

    selector = ', '.join([webelem.SELECTORS[webelem.Group.links],
                          webelem.SELECTORS[webelem.Group.prevnext]])
    browsertab.elements.find_css(selector, _prevnext_cb)
