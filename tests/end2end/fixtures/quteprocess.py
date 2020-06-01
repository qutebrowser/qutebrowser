# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Fixtures to run qutebrowser in a QProcess and communicate."""

import os
import os.path
import re
import sys
import time
import datetime
import logging
import tempfile
import contextlib
import itertools
import json

import yaml
import pytest
from PyQt5.QtCore import pyqtSignal, QUrl, qVersion

from qutebrowser.misc import ipc
from qutebrowser.utils import log, utils, javascript, qtutils
from helpers import utils as testutils
from end2end.fixtures import testprocess


instance_counter = itertools.count()


def is_ignored_qt_message(pytestconfig, message):
    """Check if the message is listed in qt_log_ignore."""
    regexes = pytestconfig.getini('qt_log_ignore')
    for regex in regexes:
        if re.search(regex, message):
            return True
    return False


def is_ignored_lowlevel_message(message):
    """Check if we want to ignore a lowlevel process output."""
    ignored_messages = [
        # https://travis-ci.org/qutebrowser/qutebrowser/jobs/157941720
        # ???
        'Xlib: sequence lost*',
        # Started appearing with Qt 5.8...
        # http://patchwork.sourceware.org/patch/10255/
        ("*_dl_allocate_tls_init: Assertion `listp->slotinfo[cnt].gen <= "
         "GL(dl_tls_generation)' failed!*"),
        # ???
        'getrlimit(RLIMIT_NOFILE) failed',
        'libpng warning: Skipped (ignored) a chunk between APNG chunks',
        # Travis CI containers don't have a /etc/machine-id
        ('*D-Bus library appears to be incorrectly set up; failed to read '
         'machine uuid: Failed to open "/etc/machine-id": No such file or '
         'directory'),
        'See the manual page for dbus-uuidgen to correct this issue.',
        # Travis CI macOS:
        # 2017-09-11 07:32:56.191 QtWebEngineProcess[5455:28501] Couldn't set
        # selectedTextBackgroundColor from default ()
        "* Couldn't set selectedTextBackgroundColor from default ()",
        # Mac Mini:
        # <<<< VTVideoEncoderSelection >>>>
        # VTSelectAndCreateVideoEncoderInstanceInternal: no video encoder
        # found for 'avc1'
        #
        # [22:32:03.636] VTSelectAndCreateVideoEncoderInstanceInternal
        # signalled err=-12908 (err) (Video encoder not available) at
        # /SourceCache/CoreMedia_frameworks/CoreMedia-1562.240/Sources/
        # VideoToolbox/VTVideoEncoderSelection.c line 1245
        #
        # [22:32:03.636] VTCompressionSessionCreate signalled err=-12908 (err)
        # (Could not select and open encoder instance) at
        # /SourceCache/CoreMedia_frameworks/CoreMedia-1562.240/Sources/
        # VideoToolbox/VTCompressionSession.c # line 946
        '*VTSelectAndCreateVideoEncoderInstanceInternal*',
        '*VTSelectAndCreateVideoEncoderInstanceInternal*',
        '*VTCompressionSessionCreate*',
        # During shutdown on AppVeyor:
        # https://ci.appveyor.com/project/qutebrowser/qutebrowser/build/master-2089/job/or4tbct1oeqsfhfm
        'QNetworkProxyFactory: factory 0x* has returned an empty result set',
        # Qt 5.10 with debug Chromium
        # [1016/155149.941048:WARNING:stack_trace_posix.cc(625)] Failed to open
        # file: /home/florian/#14687139 (deleted)
        #   Error: No such file or directory
        '  Error: No such file or directory',
        # Qt 5.7.1
        'qt.network.ssl: QSslSocket: cannot call unresolved function *',
        # Qt 5.11
        # DevTools listening on ws://127.0.0.1:37945/devtools/browser/...
        'DevTools listening on *',
        # /home/travis/build/qutebrowser/qutebrowser/.tox/py36-pyqt511-cov/lib/
        # python3.6/site-packages/PyQt5/Qt/libexec/QtWebEngineProcess:
        # /lib/x86_64-linux-gnu/libdbus-1.so.3: no version information
        # available (required by /home/travis/build/qutebrowser/qutebrowser/
        # .tox/py36-pyqt511-cov/lib/python3.6/site-packages/PyQt5/Qt/libexec/
        # ../lib/libQt5WebEngineCore.so.5)
        '*/QtWebEngineProcess: /lib/x86_64-linux-gnu/libdbus-1.so.3: no '
        'version information available (required by '
        '*/libQt5WebEngineCore.so.5)',
    ]
    return any(testutils.pattern_match(pattern=pattern, value=message)
               for pattern in ignored_messages)


def is_ignored_chromium_message(line):
    msg_re = re.compile(r"""
        \[
        (\d+:\d+:)?  # Process/Thread ID
        \d{4}/[\d.]+:  # MMDD/Time
        (?P<loglevel>[A-Z]+):  # Log level
        [^ :]+    # filename / line
        \]
        \ (?P<message>.*)  # message
    """, re.VERBOSE)
    match = msg_re.fullmatch(line)
    if match is None:
        return False

    if match.group('loglevel') == 'INFO':
        return True

    message = match.group('message')
    ignored_messages = [
        # [27289:27289:0605/195958.776146:INFO:zygote_host_impl_linux.cc(107)]
        # No usable sandbox! Update your kernel or see
        # https://chromium.googlesource.com/chromium/src/+/master/docs/linux_suid_sandbox_development.md
        # for more information on developing with the SUID sandbox. If you want
        # to live dangerously and need an immediate workaround, you can try
        # using --no-sandbox.
        'No usable sandbox! Update your kernel or see *',
        # [30981:30992:0605/200633.041364:ERROR:cert_verify_proc_nss.cc(918)]
        # CERT_PKIXVerifyCert for localhost failed err=-8179
        'CERT_PKIXVerifyCert for localhost failed err=*',
        # [1:1:0914/130428.060976:ERROR:broker_posix.cc(41)] Invalid node
        # channel message
        'Invalid node channel message',

        # Qt 5.9.3
        # [30217:30229:1124/141512.682110:ERROR:
        # cert_verify_proc_openssl.cc(212)]
        # X509 Verification error self signed certificate : 18 : 0 : 4
        'X509 Verification error self signed certificate : 18 : 0 : 4',
        # Qt 5.13
        # [27789:27805:0325/111821.127349:ERROR:ssl_client_socket_impl.cc(962)]
        # handshake failed; returned -1, SSL error code 1, net_error -202
        'handshake failed; returned -1, SSL error code 1, net_error -202',

        # Not reproducible anymore?

        'Running without the SUID sandbox! *',
        'Unable to locate theme engine in module_path: *',
        'Could not bind NETLINK socket: Address already in use',
        # Started appearing in sessions.feature with Qt 5.8...
        'Invalid node channel message *',
        # Makes tests fail on Quantumcross' machine
        ('CreatePlatformSocket() returned an error, errno=97: Address family'
         'not supported by protocol'),

        # Qt 5.9 with debug Chromium

        # [28121:28121:0605/191637.407848:WARNING:resource_bundle_qt.cpp(114)]
        # locale_file_path.empty() for locale
        'locale_file_path.empty() for locale',
        # [26598:26598:0605/191429.639416:WARNING:audio_manager.cc(317)]
        # Multiple instances of AudioManager detected
        'Multiple instances of AudioManager detected',
        # [25775:25788:0605/191240.931551:ERROR:quarantine_linux.cc(33)]
        # Could not set extended attribute user.xdg.origin.url on file
        # /tmp/pytest-of-florian/pytest-32/test_webengine_download_suffix0/
        # downloads/download.bin: Operation not supported
        ('Could not set extended attribute user.xdg.* on file *: '
         'Operation not supported*'),
        # [5947:5947:0605/192837.856931:ERROR:render_process_impl.cc(112)]
        # WebFrame LEAKED 1 TIMES
        'WebFrame LEAKED 1 TIMES',

        # Qt 5.10 with debug Chromium
        # [1016/155149.941048:WARNING:stack_trace_posix.cc(625)] Failed to open
        # file: /home/florian/#14687139 (deleted)
        #   Error: No such file or directory
        'Failed to open file: * (deleted)',

        # macOS on Travis
        # [5140:5379:0911/063441.239771:ERROR:mach_port_broker.mm(175)]
        # Unknown process 5176 is sending Mach IPC messages!
        'Unknown process * is sending Mach IPC messages!',
        # [5205:44547:0913/142945.003625:ERROR:node_controller.cc(1268)] Error
        # on receiving Mach ports FFA56F125F699ADB.E28E252911A8704B. Dropping
        # message.
        'Error on receiving Mach ports *. Dropping message.',

        # [2734:2746:1107/131154.072032:ERROR:nss_ocsp.cc(591)] No
        # URLRequestContext for NSS HTTP handler. host: ocsp.digicert.com
        'No URLRequestContext for NSS HTTP handler. host: *',

        # https://bugreports.qt.io/browse/QTBUG-66661
        # [23359:23359:0319/115812.168578:WARNING:
        # render_frame_host_impl.cc(2744)] OnDidStopLoading was called twice.
        'OnDidStopLoading was called twice.',

        # [30412:30412:0323/074933.387250:ERROR:node_channel.cc(899)] Dropping
        # message on closed channel.
        'Dropping message on closed channel.',
        # [2204:1408:0703/113804.788:ERROR:
        # gpu_process_transport_factory.cc(1019)] Lost UI shared context.
        'Lost UI shared context.',

        # Qt 5.12
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-70702
        # [32123:32123:0923/224739.457307:ERROR:in_progress_cache_impl.cc(192)]
        # Cache is not initialized, cannot RetrieveEntry.
        'Cache is not initialized, cannot RetrieveEntry.',
        'Cache is not initialized, cannot AddOrReplaceEntry.',
        # [10518:10518:0924/121250.186121:WARNING:
        # render_frame_host_impl.cc(431)]
        # InterfaceRequest was dropped, the document is no longer active:
        # content.mojom.RendererAudioOutputStreamFactory
        'InterfaceRequest was dropped, the document is no longer active: '
        'content.mojom.RendererAudioOutputStreamFactory',
        # [1920:2168:0225/112442.664:ERROR:in_progress_cache_impl.cc(124)]
        # Could not write download entries to file: C:\Users\appveyor\AppData\
        # Local\Temp\1\qutebrowser-basedir-1l3jmxq4\data\webengine\
        # in_progress_download_metadata_store
        'Could not write download entries to file: *',

        # Qt 5.13
        # [32651:32651:0325/130146.300817:WARNING:
        # render_frame_host_impl.cc(486)]
        # InterfaceRequest was dropped, the document is no longer active:
        # resource_coordinator.mojom.FrameCoordinationUnit
        'InterfaceRequest was dropped, the document is no longer active: '
        'resource_coordinator.mojom.FrameCoordinationUnit',

        # Qt 5.14
        # [1:7:1119/162200.709920:ERROR:command_buffer_proxy_impl.cc(124)]
        # ContextResult::kTransientFailure: Failed to send
        # GpuChannelMsg_CreateCommandBuffer.
        'ContextResult::kTransientFailure: Failed to send '
        'GpuChannelMsg_CreateCommandBuffer.',
        # [156330:156350:1121/120052.060701:WARNING:
        # important_file_writer.cc(97)]
        # temp file failure: /home/florian/.local/share/qutebrowser/
        # qutebrowser/QtWebEngine/Default/user_prefs.json : could not create
        # temporary file: No such file or directory (2)
        'temp file failure: */qutebrowser/qutebrowser/QtWebEngine/Default/'
        'user_prefs.json : could not create temporary file: No such file or '
        'directory (2)',
        # [156330:156330:1121/120052.602236:ERROR:
        # viz_process_transport_factory.cc(331)]
        # Switching to software compositing.
        'Switching to software compositing.',
        # [160686:160712:1121/121226.457866:ERROR:surface_manager.cc(438)]
        # Old/orphaned temporary reference to
        # SurfaceId(FrameSinkId[](5, 2), LocalSurfaceId(8, 1, 7C3A...))
        'Old/orphaned temporary reference to '
        'SurfaceId(FrameSinkId[](*), LocalSurfaceId(*))',
        # [79680:79705:0111/151113.071008:WARNING:
        # important_file_writer.cc(97)] temp file failure:
        # /tmp/qutebrowser-basedir-gwkvqpyp/data/webengine/user_prefs.json :
        # could not create temporary file: No such file or directory (2)
        # (Only in debug builds)
        # https://bugreports.qt.io/browse/QTBUG-78319
        'temp file failure: * : could not create temporary file: No such file '
        'or directory (2)',

        # Travis
        # test_ssl_error_with_contentssl_strict__true
        # [5306:5324:0417/151739.362362:ERROR:address_tracker_linux.cc(171)]
        # Could not bind NETLINK socket: Address already in use (98)
        'Could not bind NETLINK socket: Address already in use (98)',

        # Qt 5.15 with AppVeyor
        # [2968:3108:0601/123442.125:ERROR:mf_helpers.cc(14)] Error in
        # dxva_video_decode_accelerator_win.cc on line 517
        'Error in dxva_video_decode_accelerator_win.cc on line 517',
    ]
    return any(testutils.pattern_match(pattern=pattern, value=message)
               for pattern in ignored_messages)


class LogLine(testprocess.Line):

    """A parsed line from the qutebrowser log output.

    Attributes:
        timestamp/loglevel/category/module/function/line/message/levelname:
            Parsed from the log output.
        expected: Whether the message was expected or not.
    """

    def __init__(self, pytestconfig, data):
        super().__init__(data)
        try:
            line = json.loads(data)
        except ValueError:
            raise testprocess.InvalidLine(data)
        if not isinstance(line, dict):
            raise testprocess.InvalidLine(data)

        self.timestamp = datetime.datetime.fromtimestamp(line['created'])
        self.msecs = line['msecs']
        self.loglevel = line['levelno']
        self.levelname = line['levelname']
        self.category = line['name']
        self.module = line['module']
        self.function = line['funcName']
        self.line = line['lineno']
        if self.function is None and self.line == 0:
            self.line = None
        self.traceback = line.get('traceback')
        self.message = line['message']

        self.expected = is_ignored_qt_message(pytestconfig, self.message)
        self.use_color = False

    def __str__(self):
        return self.formatted_str(colorized=self.use_color)

    def formatted_str(self, colorized=True):
        """Return a formatted colorized line.

        This returns a line like qute without --json-logging would produce.

        Args:
            colorized: If True, ANSI color codes will be embedded.
        """
        r = logging.LogRecord(self.category, self.loglevel, '', self.line,
                              self.message, (), None)
        # Patch some attributes of the LogRecord
        if self.line is None:
            r.line = 0
        r.created = self.timestamp.timestamp()
        r.msecs = self.msecs
        r.module = self.module
        r.funcName = self.function

        format_str = log.EXTENDED_FMT
        format_str = format_str.replace('{asctime:8}',
                                        '{asctime:8}.{msecs:03.0f}')
        # Mark expected errors with (expected) so it's less confusing for tests
        # which expect errors but fail due to other errors.
        if self.expected and self.loglevel > logging.INFO:
            new_color = '{' + log.LOG_COLORS['DEBUG'] + '}'
            format_str = format_str.replace('{log_color}', new_color)
            format_str = re.sub(r'{levelname:(\d*)}',
                                # Leave away the padding because (expected) is
                                # longer anyway.
                                r'{levelname} (expected)', format_str)

        formatter = log.ColoredFormatter(format_str, log.DATEFMT, '{',
                                         use_colors=colorized)
        result = formatter.format(r)
        # Manually append the stringified traceback if one is present
        if self.traceback is not None:
            result += '\n' + self.traceback
        return result


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _ipc_socket: The IPC socket of the started instance.
        _webengine: Whether to use QtWebEngine
        basedir: The base directory for this instance.
        request: The request object for the current test.
        _focus_ready: Whether the main window got focused.
        _load_ready: Whether the about:blank page got loaded.
        _instance_id: A unique ID for this QuteProc instance
        _run_counter: A counter to get a unique ID for each run.

    Signals:
        got_error: Emitted when there was an error log line.
    """

    got_error = pyqtSignal()

    KEYS = ['timestamp', 'loglevel', 'category', 'module', 'function', 'line',
            'message']

    def __init__(self, request, *, parent=None):
        super().__init__(request, parent)
        self._ipc_socket = None
        self.basedir = None
        self._focus_ready = False
        self._load_ready = False
        self._instance_id = next(instance_counter)
        self._run_counter = itertools.count()

    def _is_ready(self, what):
        """Called by _parse_line if loading/focusing is done.

        When both are done, emits the 'ready' signal.
        """
        if what == 'load':
            self._load_ready = True
        elif what == 'focus':
            self._focus_ready = True
        else:
            raise ValueError("Invalid value {!r} for 'what'.".format(what))

        is_qt_5_12 = qtutils.version_check('5.12', compiled=False)
        if ((self._load_ready and self._focus_ready) or
                (self._load_ready and is_qt_5_12)):
            self._load_ready = False
            self._focus_ready = False
            self.ready.emit()

    def _process_line(self, log_line):
        """Check if the line matches any initial lines we're interested in."""
        start_okay_message_load = (
            "load status for <qutebrowser.browser.* tab_id=0 "
            "url='about:blank'>: LoadStatus.success")
        start_okay_messages_focus = [
            ## QtWebKit
            "Focus object changed: "
            "<qutebrowser.browser.* tab_id=0 url='about:blank'>",
            # when calling QApplication::sync
            "Focus object changed: "
            "<qutebrowser.browser.webkit.webview.WebView tab_id=0 url=''>",

            ## QtWebEngine
            "Focus object changed: "
            "<PyQt5.QtWidgets.QOpenGLWidget object at *>",
            # with Qt >= 5.8
            "Focus object changed: "
            "<PyQt5.QtGui.QWindow object at *>",
            # when calling QApplication::sync
            "Focus object changed: "
            "<PyQt5.QtWidgets.QWidget object at *>",
            # Qt >= 5.11
            "Focus object changed: "
            "<qutebrowser.browser.webengine.webview.WebEngineView object "
            "at *>",
            # Qt >= 5.11 with workarounds
            "Focus object changed: "
            "<PyQt5.QtQuickWidgets.QQuickWidget object at *>",
        ]

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
              testutils.pattern_match(pattern=start_okay_message_load,
                                      value=log_line.message)):
            if not self._load_ready:
                log_line.waited_for = True
            self._is_ready('load')
        elif (log_line.category == 'misc' and any(
                testutils.pattern_match(pattern=pattern,
                                        value=log_line.message)
                for pattern in start_okay_messages_focus)):
            self._is_ready('focus')
        elif (log_line.category == 'init' and
              log_line.module == 'standarddir' and
              log_line.function == 'init' and
              log_line.message.startswith('Base directory:')):
            self.basedir = log_line.message.split(':', maxsplit=1)[1].strip()
        elif self._is_error_logline(log_line):
            self.got_error.emit()

    def _parse_line(self, line):
        try:
            log_line = LogLine(self.request.config, line)
        except testprocess.InvalidLine:
            if not line.strip():
                return None
            elif (is_ignored_qt_message(self.request.config, line) or
                  is_ignored_lowlevel_message(line) or
                  is_ignored_chromium_message(line) or
                  list(self.request.node.iter_markers('no_invalid_lines'))):
                self._log("IGNORED: {}".format(line))
                return None
            else:
                raise

        log_line.use_color = self.request.config.getoption('--color') != 'no'
        verbose = self.request.config.getoption('--verbose')
        if log_line.loglevel > logging.VDEBUG or verbose:
            self._log(log_line)
        self._process_line(log_line)
        return log_line

    def _executable_args(self):
        profile = self.request.config.getoption('--qute-profile-subprocs')
        if hasattr(sys, 'frozen'):
            if profile:
                raise Exception("Can't profile with sys.frozen!")
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'qutebrowser')
            args = []
        else:
            executable = sys.executable
            if profile:
                profile_dir = os.path.join(os.getcwd(), 'prof')
                profile_id = '{}_{}'.format(self._instance_id,
                                            next(self._run_counter))
                profile_file = os.path.join(profile_dir,
                                            '{}.pstats'.format(profile_id))
                try:
                    os.mkdir(profile_dir)
                except FileExistsError:
                    pass
                args = [os.path.join('scripts', 'dev', 'run_profile.py'),
                        '--profile-tool', 'none',
                        '--profile-file', profile_file]
            else:
                args = ['-bb', '-m', 'qutebrowser']
        return executable, args

    def _default_args(self):
        backend = 'webengine' if self.request.config.webengine else 'webkit'
        args = ['--debug', '--no-err-windows', '--temp-basedir',
                '--json-logging', '--loglevel', 'vdebug',
                '--backend', backend, '--debug-flag', 'no-sql-history',
                '--debug-flag', 'werror']
        if qVersion() == '5.7.1':
            # https://github.com/qutebrowser/qutebrowser/issues/3163
            args += ['--qt-flag', 'disable-seccomp-filter-sandbox']
        args.append('about:blank')
        return args

    def path_to_url(self, path, *, port=None, https=False):
        """Get a URL based on a filename for the localhost webserver.

        URLs like about:... and qute:... are handled specially and returned
        verbatim.
        """
        special_schemes = ['about:', 'qute:', 'chrome:', 'view-source:',
                           'data:', 'http:', 'https:']
        server = self.request.getfixturevalue('server')
        server_port = server.port if port is None else port

        if any(path.startswith(scheme) for scheme in special_schemes):
            path = path.replace('(port)', str(server_port))
            return path
        else:
            return '{}://localhost:{}/{}'.format(
                'https' if https else 'http',
                server_port,
                path if path != '/' else '')

    def wait_for_js(self, message):
        """Wait for the given javascript console message.

        Return:
            The LogLine.
        """
        line = self.wait_for(category='js',
                             message='[*] {}'.format(message))
        line.expected = True
        return line

    def wait_scroll_pos_changed(self, x=None, y=None):
        """Wait until a "Scroll position changed" message was found.

        With QtWebEngine, on older Qt versions which lack
        QWebEnginePage.scrollPositionChanged, this also skips the test.
        """
        __tracebackhide__ = (lambda e:
                             e.errisinstance(testprocess.WaitForTimeout))
        if (x is None and y is not None) or (y is None and x is not None):
            raise ValueError("Either both x/y or neither must be given!")

        if x is None and y is None:
            point = 'PyQt5.QtCore.QPoint(*, *)'  # not counting 0/0 here
        elif x == '0' and y == '0':
            point = 'PyQt5.QtCore.QPoint()'
        else:
            point = 'PyQt5.QtCore.QPoint({}, {})'.format(x, y)
        self.wait_for(category='webview',
                      message='Scroll position changed to ' + point)

    def wait_for(self, timeout=None,  # pylint: disable=arguments-differ
                 **kwargs):
        """Extend wait_for to add divisor if a test is xfailing."""
        __tracebackhide__ = (lambda e:
                             e.errisinstance(testprocess.WaitForTimeout))
        xfail = self.request.node.get_closest_marker('xfail')
        if xfail and (not xfail.args or xfail.args[0]):
            kwargs['divisor'] = 10
        else:
            kwargs['divisor'] = 1
        return super().wait_for(timeout=timeout, **kwargs)

    def _is_error_logline(self, msg):
        """Check if the given LogLine is some kind of error message."""
        is_js_error = (msg.category == 'js' and
                       testutils.pattern_match(pattern='[*] [FAIL] *',
                                               value=msg.message))
        # Try to complain about the most common mistake when accidentally
        # loading external resources.
        is_ddg_load = testutils.pattern_match(
            pattern="load status for <* tab_id=* url='*duckduckgo*'>: *",
            value=msg.message)

        is_log_error = (msg.loglevel > logging.INFO and
                        not msg.message.startswith("Ignoring world ID") and
                        not msg.message.startswith(
                            "Could not initialize QtNetwork SSL support."))
        return is_log_error or is_js_error or is_ddg_load

    def _maybe_skip(self):
        """Skip the test if [SKIP] lines were logged."""
        skip_texts = []

        for msg in self._data:
            if (msg.category == 'js' and
                    testutils.pattern_match(pattern='[*] [SKIP] *',
                                            value=msg.message)):
                skip_texts.append(msg.message.partition(' [SKIP] ')[2])

        if skip_texts:
            pytest.skip(', '.join(skip_texts))

    def before_test(self):
        """Clear settings before every test."""
        super().before_test()
        self.send_cmd(':config-clear')
        self._init_settings()
        self.clear_data()

    def _init_settings(self):
        """Adjust some qutebrowser settings after starting."""
        settings = [
            ('messages.timeout', '0'),
            ('auto_save.interval', '0'),
            ('new_instance_open_target_window', 'last-opened')
        ]
        if not self.request.config.webengine:
            settings.append(('content.ssl_strict', 'false'))

        for opt, value in settings:
            self.set_setting(opt, value)

    def after_test(self):
        """Handle unexpected/skip logging and clean up after each test."""
        __tracebackhide__ = lambda e: e.errisinstance(pytest.fail.Exception)
        bad_msgs = [msg for msg in self._data
                    if self._is_error_logline(msg) and not msg.expected]

        try:
            call = self.request.node.rep_call
        except AttributeError:
            pass
        else:
            if call.failed or hasattr(call, 'wasxfail'):
                super().after_test()
                return

        try:
            if bad_msgs:
                text = 'Logged unexpected errors:\n\n' + '\n'.join(
                    str(e) for e in bad_msgs)
                # We'd like to use pytrace=False here but don't as a WORKAROUND
                # for https://github.com/pytest-dev/pytest/issues/1316
                pytest.fail(text)
            else:
                self._maybe_skip()
        finally:
            super().after_test()

    def send_ipc(self, commands, target_arg=''):
        """Send a raw command to the running IPC socket."""
        delay = self.request.config.getoption('--qute-delay')
        time.sleep(delay / 1000)

        assert self._ipc_socket is not None
        ipc.send_to_running_instance(self._ipc_socket, commands, target_arg)
        self.wait_for(category='ipc', module='ipc', function='on_ready_read',
                      message='Read from socket *')

    def start(self, *args, wait_focus=True,
              **kwargs):  # pylint: disable=arguments-differ
        if not wait_focus:
            self._focus_ready = True

        try:
            super().start(*args, **kwargs)
        except testprocess.ProcessExited:
            is_dl_inconsistency = str(self.captured_log[-1]).endswith(
                "_dl_allocate_tls_init: Assertion "
                "`listp->slotinfo[cnt].gen <= GL(dl_tls_generation)' failed!")
            if 'TRAVIS' in os.environ and is_dl_inconsistency:
                # WORKAROUND for https://sourceware.org/bugzilla/show_bug.cgi?id=19329
                self.captured_log = []
                self._log("NOTE: Restarted after libc DL inconsistency!")
                self.clear_data()
                super().start(*args, **kwargs)
            else:
                raise

    def send_cmd(self, command, count=None, invalid=False, *, escape=True):
        """Send a command to the running qutebrowser instance.

        Args:
            count: The count to pass to the command.
            invalid: If True, we don't wait for "command called: ..." in the
                     log and return None.
            escape: Escape backslashes in the command

        Return:
            The parsed log line with "command called: ..." or None.
        """
        summary = command
        if count is not None:
            summary += ' (count {})'.format(count)
        self.log_summary(summary)

        if escape:
            command = command.replace('\\', r'\\')

        if count is not None:
            command = ':run-with-count {} {}'.format(count,
                                                     command.lstrip(':'))

        self.send_ipc([command])
        if invalid:
            return None
        else:
            return self.wait_for(category='commands', module='command',
                                 function='run', message='command called: *')

    def get_setting(self, opt, pattern=None):
        """Get the value of a qutebrowser setting."""
        if pattern is None:
            cmd = ':set {}?'.format(opt)
        else:
            cmd = ':set -u {} {}?'.format(pattern, opt)

        self.send_cmd(cmd)
        msg = self.wait_for(loglevel=logging.INFO, category='message',
                            message='{} = *'.format(opt))

        if pattern is None:
            return msg.message.split(' = ')[1]
        else:
            return msg.message.split(' = ')[1].split(' for ')[0]

    def set_setting(self, option, value):
        # \ and " in a value should be treated literally, so escape them
        value = value.replace('\\', r'\\')
        value = value.replace('"', '\\"')
        self.send_cmd(':set -t "{}" "{}"'.format(option, value), escape=False)
        self.wait_for(category='config', message='Config option changed: *')

    @contextlib.contextmanager
    def temp_setting(self, opt, value):
        """Context manager to set a setting and reset it on exit."""
        old_value = self.get_setting(opt)
        self.set_setting(opt, value)
        yield
        self.set_setting(opt, old_value)

    def open_path(self, path, *, new_tab=False, new_bg_tab=False,
                  new_window=False, private=False, as_url=False, port=None,
                  https=False, wait=True):
        """Open the given path on the local webserver in qutebrowser."""
        url = self.path_to_url(path, port=port, https=https)
        self.open_url(url, new_tab=new_tab, new_bg_tab=new_bg_tab,
                      new_window=new_window, private=private, as_url=as_url,
                      wait=wait)

    def open_url(self, url, *, new_tab=False, new_bg_tab=False,
                 new_window=False, private=False, as_url=False, wait=True):
        """Open the given url in qutebrowser."""
        if sum(1 for opt in [new_tab, new_bg_tab, new_window, private, as_url]
               if opt) > 1:
            raise ValueError("Conflicting options given!")

        if as_url:
            self.send_cmd(url, invalid=True)
            line = None
        elif new_tab:
            line = self.send_cmd(':open -t ' + url)
        elif new_bg_tab:
            line = self.send_cmd(':open -b ' + url)
        elif new_window:
            line = self.send_cmd(':open -w ' + url)
        elif private:
            line = self.send_cmd(':open -p ' + url)
        else:
            line = self.send_cmd(':open ' + url)

        if wait:
            self.wait_for_load_finished_url(url, after=line)

    def mark_expected(self, category=None, loglevel=None, message=None):
        """Mark a given logging message as expected."""
        line = self.wait_for(category=category, loglevel=loglevel,
                             message=message)
        line.expected = True

    def wait_for_load_finished_url(self, url, *, timeout=None,
                                   load_status='success', after=None):
        """Wait until a URL has finished loading."""
        __tracebackhide__ = (lambda e: e.errisinstance(
            testprocess.WaitForTimeout))

        if timeout is None:
            if 'CI' in os.environ:
                timeout = 15000
            else:
                timeout = 5000

        qurl = QUrl(url)
        if not qurl.isValid():
            raise ValueError("Invalid URL {}: {}".format(url,
                                                         qurl.errorString()))

        if (qurl == QUrl('about:blank') and
                not qtutils.version_check('5.10', compiled=False)):
            # For some reason, we don't get a LoadStatus.success for
            # about:blank sometimes.
            # However, if we do this for Qt 5.10, we get general testsuite
            # instability as site loads get reported with about:blank...
            pattern = "Changing title for idx * to 'about:blank'"
        else:
            # We really need the same representation that the webview uses in
            # its __repr__
            url = utils.elide(qurl.toDisplayString(QUrl.EncodeUnicode), 100)
            assert url

            pattern = re.compile(
                r"(load status for <qutebrowser\.browser\..* "
                r"tab_id=\d+ url='{url}/?'>: LoadStatus\.{load_status}|fetch: "
                r"PyQt5\.QtCore\.QUrl\('{url}'\) -> .*)".format(
                    load_status=re.escape(load_status), url=re.escape(url)))

        try:
            self.wait_for(message=pattern, timeout=timeout, after=after)
        except testprocess.WaitForTimeout:
            raise testprocess.WaitForTimeout("Timed out while waiting for {} "
                                             "to be loaded".format(url))

    def wait_for_load_finished(self, path, *, port=None, https=False,
                               timeout=None, load_status='success'):
        """Wait until a path has finished loading."""
        __tracebackhide__ = (lambda e: e.errisinstance(
            testprocess.WaitForTimeout))
        url = self.path_to_url(path, port=port, https=https)
        self.wait_for_load_finished_url(url, timeout=timeout,
                                        load_status=load_status)

    def get_session(self):
        """Save the session and get the parsed session data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = os.path.join(tmpdir, 'session.yml')
            self.send_cmd(':session-save --with-private "{}"'.format(session))
            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Saved session {}.'.format(session))
            with open(session, encoding='utf-8') as f:
                data = f.read()

        self._log('\nCurrent session data:\n' + data)
        return utils.yaml_load(data)

    def get_content(self, plain=True):
        """Get the contents of the current page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'page')

            if plain:
                self.send_cmd(':debug-dump-page --plain "{}"'.format(path))
            else:
                self.send_cmd(':debug-dump-page "{}"'.format(path))

            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Dumped page to {}.'.format(path))

            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    def press_keys(self, keys):
        """Press the given keys using :fake-key."""
        self.send_cmd(':fake-key -g "{}"'.format(keys))

    def click_element_by_text(self, text):
        """Click the element with the given text."""
        # Use Javascript and XPath to find the right element, use console.log
        # to return an error (no element found, ambiguous element)
        script = (
            'var _es = document.evaluate(\'//*[text()={text}]\', document, '
            'null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);'
            'if (_es.snapshotLength == 0) {{ console.log("qute:no elems"); }} '
            'else if (_es.snapshotLength > 1) {{ console.log("qute:ambiguous '
            'elems") }} '
            'else {{ console.log("qute:okay"); _es.snapshotItem(0).click() }}'
        ).format(text=javascript.string_escape(_xpath_escape(text)))
        self.send_cmd(':jseval ' + script, escape=False)
        message = self.wait_for_js('qute:*').message
        if message.endswith('qute:no elems'):
            raise ValueError('No element with {!r} found'.format(text))
        if message.endswith('qute:ambiguous elems'):
            raise ValueError('Element with {!r} is not unique'.format(text))
        if not message.endswith('qute:okay'):
            raise ValueError('Invalid response from qutebrowser: {}'
                             .format(message))

    def compare_session(self, expected):
        """Compare the current sessions against the given template.

        partial_compare is used, which means only the keys/values listed will
        be compared.
        """
        __tracebackhide__ = lambda e: e.errisinstance(pytest.fail.Exception)
        data = self.get_session()
        expected = yaml.load(expected, Loader=YamlLoader)
        outcome = testutils.partial_compare(data, expected)
        if not outcome:
            msg = "Session comparison failed: {}".format(outcome.error)
            msg += '\nsee stdout for details'
            pytest.fail(msg)

    def turn_on_scroll_logging(self, no_scroll_filtering=False):
        """Make sure all scrolling changes are logged."""
        cmd = ":debug-pyeval -q objects.debug_flags.add('{}')"
        if no_scroll_filtering:
            self.send_cmd(cmd.format('no-scroll-filtering'))
        self.send_cmd(cmd.format('log-scroll-pos'))


class YamlLoader(yaml.SafeLoader):

    """Custom YAML loader used in compare_session."""


# Translate ... to ellipsis in YAML.
YamlLoader.add_constructor('!ellipsis', lambda loader, node: ...)
YamlLoader.add_implicit_resolver('!ellipsis', re.compile(r'\.\.\.'), None)


def _xpath_escape(text):
    """Escape a string to be used in an XPath expression.

    The resulting string should still be escaped with javascript.string_escape,
    to prevent javascript from interpreting the quotes.

    This function is needed because XPath does not provide any character
    escaping mechanisms, so to get the string
        "I'm back", he said
    you have to use concat like
        concat('"I', "'m back", '", he said')

    Args:
        text: Text to escape

    Return:
        The string "escaped" as a concat() call.
    """
    # Shortcut if at most a single quoting style is used
    if "'" not in text or '"' not in text:
        return repr(text)
    parts = re.split('([\'"])', text)
    # Python's repr() of strings will automatically choose the right quote
    # type. Since each part only contains one "type" of quote, no escaping
    # should be necessary.
    parts = [repr(part) for part in parts if part]
    return 'concat({})'.format(', '.join(parts))


@pytest.fixture(scope='module')
def quteproc_process(qapp, server, request):
    """Fixture for qutebrowser process which is started once per file."""
    # Passing request so it has an initial config
    proc = QuteProc(request)
    proc.start()
    yield proc
    proc.terminate()


@pytest.fixture
def quteproc(quteproc_process, server, request):
    """Per-test qutebrowser fixture which uses the per-file process."""
    request.node._quteproc_log = quteproc_process.captured_log
    quteproc_process.before_test()
    quteproc_process.request = request
    yield quteproc_process
    quteproc_process.after_test()


@pytest.fixture
def quteproc_new(qapp, server, request):
    """Per-test qutebrowser process to test invocations."""
    proc = QuteProc(request)
    request.node._quteproc_log = proc.captured_log
    # Not calling before_test here as that would start the process
    yield proc
    proc.after_test()
    proc.terminate()
