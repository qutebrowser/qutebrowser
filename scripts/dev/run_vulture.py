#!/usr/bin/env python

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Run vulture on the source files and filter out false-positives."""

import sys
import os
import re
import tempfile
import inspect
import argparse

import vulture

import qutebrowser.app  # pylint: disable=unused-import
from qutebrowser.extensions import loader
from qutebrowser.misc import objects, sql, nativeeventfilter
from qutebrowser.utils import utils, version, qtutils
# To run the decorators from there
# pylint: disable=unused-import
from qutebrowser.browser.webkit.network import webkitqutescheme
# pylint: enable=unused-import
from qutebrowser.browser import qutescheme
from qutebrowser.config import configtypes


def whitelist_generator():  # noqa: C901
    """Generator which yields lines to add to a vulture whitelist."""
    loader.load_components(skip_hooks=True)

    # qutebrowser commands
    for cmd in objects.commands.values():
        yield utils.qualname(cmd.handler)

    # PyQt properties
    yield 'qutebrowser.mainwindow.statusbar.bar.StatusBar.color_flags'
    yield 'qutebrowser.mainwindow.statusbar.url.UrlText.urltype'

    # Not used yet, but soon (or when debugging)
    yield 'qutebrowser.utils.debug.log_events'
    yield 'qutebrowser.utils.debug.log_signals'
    yield 'qutebrowser.utils.debug.qflags_key'
    yield 'qutebrowser.utils.qtutils.QtOSError.qt_errno'
    yield 'scripts.utils.bg_colors'
    yield 'qutebrowser.misc.sql.SqliteErrorCode.CONSTRAINT'
    yield 'qutebrowser.misc.throttle.Throttle.set_delay'
    yield 'qutebrowser.misc.guiprocess.GUIProcess.stderr'

    # Qt attributes
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().baseUrl'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().content'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().encoding'
    yield 'PyQt5.QtWebKit.QWebPage.ErrorPageExtensionReturn().fileNames'
    yield 'PyQt5.QtWidgets.QStyleOptionViewItem.backgroundColor'

    ## qute://... handlers
    for name in qutescheme._HANDLERS:  # pylint: disable=protected-access
        name = name.replace('-', '_')
        yield 'qutebrowser.browser.qutescheme.qute_' + name

    # Other false-positives
    yield 'qutebrowser.completion.models.listcategory.ListCategory().lessThan'
    yield 'qutebrowser.utils.jinja.Loader.get_source'
    yield 'qutebrowser.utils.log.QtWarningFilter.filter'
    yield 'qutebrowser.browser.pdfjs.is_available'
    yield 'qutebrowser.utils.usertypes.ExitStatus.reserved'
    yield 'QEvent.posted'
    yield 'log_stack'  # from message.py
    yield 'propagate'  # logging.getLogger('...).propagate = False
    # vulture doesn't notice the hasattr() and thus thinks netrc_used is unused
    # in NetworkManager.on_authentication_required
    yield 'PyQt5.QtNetwork.QNetworkReply.netrc_used'
    yield 'qutebrowser.browser.downloads.last_used_directory'
    yield 'PaintContext.clip'  # from completiondelegate.py
    yield 'logging.LogRecord.log_color'  # from logging.py
    yield 'scripts.utils.use_color'  # from asciidoc2html.py
    for attr in ['pyeval_output', 'log_clipboard', 'fake_clipboard']:
        yield 'qutebrowser.misc.utilcmds.' + attr

    for attr in ['fileno', 'truncate', 'closed', 'readable']:
        yield 'qutebrowser.utils.qtutils.PyQIODevice.' + attr

    for attr in ['msgs', 'priority', 'visit_attribute']:
        yield 'scripts.dev.pylint_checkers.config.' + attr

    for name, _member in inspect.getmembers(configtypes, inspect.isclass):
        yield 'qutebrowser.config.configtypes.' + name
    yield 'qutebrowser.config.configexc.ConfigErrorDesc.traceback'
    yield 'qutebrowser.config.configfiles.ConfigAPI.load_autoconfig'
    yield 'types.ModuleType.c'  # configfiles:read_config_py
    for name in ['configdir', 'datadir']:
        yield 'qutebrowser.config.configfiles.ConfigAPI.' + name

    yield 'include_aliases'

    for attr in ['_get_default_metavar_for_optional',
                 '_get_default_metavar_for_positional', '_metavar_formatter']:
        yield 'scripts.dev.src2asciidoc.UsageFormatter.' + attr
    yield 'scripts.dev.build_release.pefile.PE.OPTIONAL_HEADER.CheckSum'

    for dist in version.Distribution:
        yield 'qutebrowser.utils.version.Distribution.{}'.format(dist.name)

    for opcode in nativeeventfilter.XcbInputOpcodes:
        yield f'qutebrowser.misc.nativeeventfilter.XcbInputOpcodes.{opcode.name}'

    # attrs
    yield 'qutebrowser.browser.webkit.network.networkmanager.ProxyId.hostname'
    yield 'qutebrowser.command.command.ArgInfo._validate_exclusive'
    yield 'scripts.get_coredumpctl_traces.Line.uid'
    yield 'scripts.get_coredumpctl_traces.Line.gid'
    yield 'scripts.importer.import_moz_places.places.row_factory'

    # component hooks
    yield 'qutebrowser.components.hostblock.on_lists_changed'
    yield 'qutebrowser.components.braveadblock.on_lists_changed'
    yield 'qutebrowser.components.hostblock.on_method_changed'
    yield 'qutebrowser.components.braveadblock.on_method_changed'

    # used in type comments
    yield 'pending_download_type'
    yield 'world_id_type'
    yield 'ParserDictType'
    yield 'qutebrowser.config.configutils.Values._VmapKeyType'

    # used in tests
    yield 'qutebrowser.qt.machinery.SelectionReason.fake'

    # ELF
    yield 'qutebrowser.misc.elf.Endianness.big'
    for name in ['phoff', 'ehsize', 'phentsize', 'phnum']:
        yield f'qutebrowser.misc.elf.Header.{name}'
    for name in ['addr', 'addralign', 'entsize']:
        yield f'qutebrowser.misc.elf.SectionHeader.{name}'

    # For completeness
    for name in list(qtutils.LibraryPath):
        yield f'qutebrowser.utils.qtutils.LibraryPath.{name}'

    for name in list(sql.SqliteErrorCode):
        yield f'qutebrowser.misc.sql.SqliteErrorCode.{name}'


def filter_func(item):
    """Check if a missing function should be filtered or not.

    Return:
        True if the missing function should be filtered/ignored, False
        otherwise.
    """
    return bool(re.fullmatch(r'[a-z]+[A-Z][a-zA-Z]+', item.name))


def report(items):
    """Generate a report based on the given vulture.Item's.

    Based on vulture.Vulture.report, but we can't use that as we can't set the
    properties which get used for the items.
    """
    output = []
    for item in sorted(items, key=lambda e: (str(e.filename).lower(), e.first_lineno)):
        output.append(item.get_report())
    return output


def run(files):
    """Run vulture over the given files."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as whitelist_file:
        for line in whitelist_generator():
            whitelist_file.write(line + '\n')

        whitelist_file.close()

        vult = vulture.Vulture(verbose=False)
        vult.scavenge(
            files + [whitelist_file.name],
            exclude=["qutebrowser/qt/_core_pyqtproperty.py",
                     "qutebrowser/config/configcontainer.py"],
        )

        os.remove(whitelist_file.name)

    filters = {
        'unused_funcs': filter_func,
        'unused_props': lambda item: False,
        'unused_vars': lambda item: False,
        'unused_attrs': lambda item: False,
    }

    items = []

    for attr, func in filters.items():
        sub_items = getattr(vult, attr)
        for item in sub_items:
            filtered = func(item)
            if not filtered:
                items.append(item)

    return report(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*', default=['qutebrowser', 'scripts',
                                                     'setup.py'])
    args = parser.parse_args()
    out = run(args.files)
    for line in out:
        print(line)
    sys.exit(bool(out))


if __name__ == '__main__':
    main()
