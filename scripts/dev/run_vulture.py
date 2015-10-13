#!/usr/bin/env python
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Run vulture on the source files and filter out false-positives."""

import sys
import os
import re
import tempfile
import inspect

import vulture

import qutebrowser.app  # pylint: disable=unused-import
from qutebrowser.commands import cmdutils
from qutebrowser.utils import utils
from qutebrowser.browser import rfc6266


def whitelist_generator():
    """Generator which yields lines to add to a vulture whitelist."""
    # qutebrowser commands
    for cmd in cmdutils.cmd_dict.values():
        yield utils.qualname(cmd.handler)

    # pyPEG2 classes
    for name, member in inspect.getmembers(rfc6266, inspect.isclass):
        for attr in ('grammar', 'regex'):
            if hasattr(member, attr):
                yield 'qutebrowser.browser.rfc6266.{}.{}'.format(name, attr)

    # PyQt properties
    for attr in ('prompt_active', 'command_active', 'insert_active',
                 'caret_mode'):
        yield 'qutebrowser.mainwindow.statusbar.bar.StatusBar.' + attr
    yield 'qutebrowser.mainwindow.statusbar.url.UrlText.urltype'

    # Not used yet, but soon (or when debugging)
    yield 'qutebrowser.config.configtypes.Regex'
    yield 'qutebrowser.utils.debug.log_events'
    yield 'qutebrowser.utils.debug.log_signals'
    yield 'qutebrowser.utils.debug.qflags_key'
    yield 'qutebrowser.utils.qtutils.QtOSError.qt_errno'
    yield 'qutebrowser.utils.usertypes.NeighborList.firstitem'
    yield 'scripts.utils.bg_colors'
    yield 'scripts.utils.print_subtitle'

    # Qt attributes
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().baseUrl'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().content'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().encoding'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().fileNames'
    yield 'PyQt5.QtGui.QAbstractTextDocumentLayout.PaintContext().clip'
    yield 'PyQt5.QtWidgets.QStyleOptionViewItem.backgroundColor'

    # Globals
    # https://bitbucket.org/jendrikseipp/vulture/issues/10/
    yield 'qutebrowser.misc.utilcmds.pyeval_output'
    yield 'utils.use_color'

    # Other false-positives
    yield ('qutebrowser.completion.models.sortfilter.CompletionFilterModel().'
           'lessThan')
    yield 'qutebrowser.utils.jinja.Loader.get_source'
    yield 'qutebrowser.utils.log.VDEBUG'
    yield 'qutebrowser.utils.log.QtWarningFilter.filter'
    yield 'logging.LogRecord.log_color'

    for attr in ('fileno', 'truncate', 'closed', 'readable'):
        yield 'qutebrowser.utils.qtutils.PyQIODevice.' + attr

    for attr in ('priority', 'visit_callfunc'):
        yield 'scripts.dev.pylint_checkers.config.' + attr

    yield 'scripts.dev.pylint_checkers.modeline.process_module'

    for attr in ('_get_default_metavar_for_optional',
                 '_get_default_metavar_for_positional',
                 '_metavar_formatter'):
        yield 'scripts.dev.src2asciidoc.UsageFormatter.' + attr


def filter_func(item):
    """Check if a missing function should be filtered or not.

    Return:
        True if the missing function should be filtered/ignored, False
        otherwise.
    """
    if re.match(r'[a-z]+[A-Z][a-zA-Z]+', str(item)):
        # probably a virtual Qt method
        return True
    else:
        return False


def report(items):
    """Generate a report based on the given vulture.Item's.

    Based on vulture.Vulture.report, but we can't use that as we can't set the
    properties which get used for the items.
    """
    unused_item_found = False
    for item in sorted(items, key=lambda e: (e.file.lower(), e.lineno)):
        relpath = os.path.relpath(item.file)
        path = relpath if not relpath.startswith('..') else item.file
        print("%s:%d: Unused %s '%s'" % (path, item.lineno, item.typ,
                                         item))
        unused_item_found = True
    return unused_item_found


def main():
    """Run vulture over all files."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as whitelist_file:
        for line in whitelist_generator():
            whitelist_file.write(line + '\n')

        whitelist_file.close()

        vult = vulture.Vulture(exclude=[], verbose=False)
        vult.scavenge(['qutebrowser', 'scripts', whitelist_file.name])

        os.remove(whitelist_file.name)

    filters = {
        'unused_funcs': filter_func,
        'unused_props': lambda: False,
        'unused_vars': lambda: False,
        'unused_attrs': lambda: False,
    }

    items = []

    for attr, func in filters.items():
        sub_items = getattr(vult, attr)
        for item in sub_items:
            filtered = func(item)
            if not filtered:
                items.append(item)

    sys.exit(report(items))


if __name__ == '__main__':
    main()
