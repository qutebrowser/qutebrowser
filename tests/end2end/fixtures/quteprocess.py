# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fixtures to run qutebrowser in a QProcess and communicate."""

import pathlib
import os
import re
import sys
import time
import datetime
import logging
import tempfile
import contextlib
import itertools
import collections
import json

import yaml
import pytest
from PIL.ImageGrab import grab
from qutebrowser.qt.core import pyqtSignal, QUrl, QPoint
from qutebrowser.qt.gui import QImage, QColor

from qutebrowser.misc import ipc
from qutebrowser.utils import log, utils, javascript
from helpers import testutils
from end2end.fixtures import testprocess


instance_counter = itertools.count()


def is_ignored_qt_message(pytestconfig, message):
    """Check if the message is listed in qt_log_ignore."""
    regexes = pytestconfig.getini('qt_log_ignore')
    return any(re.search(regex, message) for regex in regexes)


def is_ignored_lowlevel_message(message):
    """Check if we want to ignore a lowlevel process output."""
    ignored_messages = [
        # Qt 6.2 / 6.3
        'Fontconfig error: Cannot load default config file: No such file: (null)',
        'Fontconfig error: Cannot load default config file',

        # Qt 6.4, from certificate error below, but on separate lines
        '----- Certificate i=0 (*,CN=localhost,O=qutebrowser test certificate) -----',
        'ERROR: No matching issuer found',

        # Qt 6.5 debug, overflow/linebreak from a JS message...
        # IGNORED: [678403:678403:0315/203342.008878:INFO:CONSOLE(65)] "Refused
        # to apply inline style because it violates the following Content
        # Security Policy directive: "default-src none". Either the
        # 'unsafe-inline' keyword, a hash
        # ('sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='), or a nonce
        # ('nonce-...') is required to enable inline execution. Note also that
        # 'style-src' was not explicitly set, so 'default-src' is used as a
        # fallback.
        # INVALID: ", source: userscript:_qute_stylesheet (65)
        '", source: userscript:_qute_stylesheet (*)',

        # Randomly started showing up on Qt 5.15.2
        'QPaintDevice: Cannot destroy paint device that is being painted',

        # Qt 6.6 on GitHub Actions
        (
            'libva error: vaGetDriverNameByIndex() failed with unknown libva error, '
            'driver_name = (null)'
        ),
        'libva error: vaGetDriverNames() failed with unknown libva error',

        # Mesa 23.3
        # See https://gitlab.freedesktop.org/mesa/mesa/-/issues/10293
        'MESA: error: ZINK: vkCreateInstance failed (VK_ERROR_INCOMPATIBLE_DRIVER)',
        'glx: failed to create drisw screen',
        'failed to load driver: zink',
        'DRI3 not available',
        # Webkit on arch with a newer mesa
        'MESA: error: ZINK: failed to load libvulkan.so.1',

        # GitHub Actions with Archlinux unstable packages
        'libEGL warning: DRI3: Screen seems not DRI3 capable',
        'libEGL warning: egl: failed to create dri2 screen',
        'libEGL warning: DRI3 error: Could not get DRI3 device',
        'libEGL warning: Activate DRI3 at Xorg or build mesa with DRI2',
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
        # GitHub Actions with Qt 5.15.2
        'SharedImageManager::ProduceGLTexture: Trying to produce a representation from a non-existent mailbox. *',
        ('[.DisplayCompositor]GL ERROR :GL_INVALID_OPERATION : '
         'DoCreateAndTexStorage2DSharedImageINTERNAL: invalid mailbox name'),
        ('[.DisplayCompositor]GL ERROR :GL_INVALID_OPERATION : '
         'DoBeginSharedImageAccessCHROMIUM: bound texture is not a shared image'),
        ('[.DisplayCompositor]RENDER WARNING: texture bound to texture unit 0 is '
         'not renderable. It might be non-power-of-2 or have incompatible texture '
         'filtering (maybe)?'),
        ('[.DisplayCompositor]GL ERROR :GL_INVALID_OPERATION : '
         'DoEndSharedImageAccessCHROMIUM: bound texture is not a shared image'),

        # [916:934:1213/080738.912432:ERROR:address_tracker_linux.cc(214)] Could not bind NETLINK socket: Address already in use (98)
        'Could not bind NETLINK socket: Address already in use (98)',

        # Flatpak with data/crashers/webrtc.html (Qt 6.2)
        # [9044:9113:0512/012126.284773:ERROR:mdns_responder.cc(868)] mDNS responder manager failed to start.
        # [9044:9113:0512/012126.284818:ERROR:mdns_responder.cc(885)] The mDNS responder manager is not started yet.
        'mDNS responder manager failed to start.',
        'The mDNS responder manager is not started yet.',

        # Qt 6.2:
        # [503633:503650:0509/185222.442798:ERROR:ssl_client_socket_impl.cc(959)] handshake failed; returned -1, SSL error code 1, net_error -202
        'handshake failed; returned -1, SSL error code 1, net_error -202',
        # Qt 6.8 + Python 3.14
        'handshake failed; returned -1, SSL error code 1, net_error -101',

        # Qt 6.2:
        # [2432160:7:0429/195800.168435:ERROR:command_buffer_proxy_impl.cc(140)] ContextResult::kTransientFailure: Failed to send GpuChannelMsg_CreateCommandBuffer.
        # Qt 6.3:
        # [2435381:7:0429/200014.168057:ERROR:command_buffer_proxy_impl.cc(125)] ContextResult::kTransientFailure: Failed to send GpuControl.CreateCommandBuffer.
        'ContextResult::kTransientFailure: Failed to send *CreateCommandBuffer.',

        # Qt 6.3:
        # [4919:8:0530/170658.033287:ERROR:command_buffer_proxy_impl.cc(328)] GPU state invalid after WaitForGetOffsetInRange.
        'GPU state invalid after WaitForGetOffsetInRange.',
        # [5469:5503:0621/183219.878182:ERROR:backend_impl.cc(1414)] Unable to map Index file
        'Unable to map Index file',

        # Qt 6.4:
        # [2456284:2456339:0715/110322.570154:ERROR:cert_verify_proc_builtin.cc(681)] CertVerifyProcBuiltin for localhost failed:
        # ----- Certificate i=0 (1.2.840.113549.1.9.1=#6D61696C407175746562726F777365722E6F7267,CN=localhost,O=qutebrowser test certificate) -----
        # ERROR: No matching issuer found
        # (Note, subsequent lines above in is_ignored_lowlevel_message)
        'CertVerifyProcBuiltin for localhost failed:',
        # [320667:320667:1124/135621.718232:ERROR:interface_endpoint_client.cc(687)] Message 4 rejected by interface blink.mojom.WidgetHost
        'Message 4 rejected by interface blink.mojom.WidgetHost',


        # Qt 5.15.1 debug build (Chromium 83)
        # '[314297:7:0929/214605.491958:ERROR:context_provider_command_buffer.cc(145)]
        # GpuChannelHost failed to create command buffer.'
        # Still present on Qt 6.5
        'GpuChannelHost failed to create command buffer.',

        # Qt 6.5 debug build
        # [640812:640865:0315/200415.708148:WARNING:important_file_writer.cc(185)]
        # Failed to create temporary file to update
        # /tmp/qutebrowser-basedir-3kvto2eq/data/webengine/user_prefs.json: No
        # such file or directory (2)
        # [640812:640864:0315/200415.715398:WARNING:important_file_writer.cc(185)]
        # Failed to create temporary file to update
        # /tmp/qutebrowser-basedir-3kvto2eq/data/webengine/Network Persistent
        # State: No such file or directory (2)
        'Failed to create temporary file to update *user_prefs.json: No such file or directory (2)',
        'Failed to create temporary file to update *Network Persistent State: No such file or directory (2)',

        # Qt 6.5 debug build
        # [645145:645198:0315/200704.324733:WARNING:simple_synchronous_entry.cc(1438)]
        "Could not open platform files for entry.",

        # Qt 6.5 debug build
        # [664320:664320:0315/202235.943899:ERROR:node_channel.cc(861)]
        # Dropping message on closed channel.
        "Dropping message on closed channel.",

        # Qt 6.5 debug build
        # tests/end2end/features/test_misc_bdd.py::test_webrtc_renderer_process_crash
        # [679056:14:0315/203418.631075:WARNING:media_session.cc(949)] RED
        # codec red is missing an associated payload type.
        "RED codec red is missing an associated payload type.",

        # Qt 6.5 debug build
        # tests/end2end/features/test_javascript_bdd.py::test_error_pages_without_js_enabled
        # and others using internal URL schemes?
        # [677785:1:0315/203308.328104:ERROR:html_media_element.cc(4874)]
        # SetError: {code=4, message="MEDIA_ELEMENT_ERROR: Media load rejected
        # by URL safety check"}
        'SetError: {code=4, message="MEDIA_ELEMENT_ERROR: Media load rejected by URL safety check"}',

        # Qt 6.5 debug build
        # [714871:715010:0315/205751.155681:ERROR:surface_manager.cc(419)]
        # Old/orphaned temporary reference to SurfaceId(FrameSinkId[](14, 3),
        # LocalSurfaceId(3, 1, 5D04...))
        "Old/orphaned temporary reference to SurfaceId(FrameSinkId[](*, *), LocalSurfaceId(*, *, *...))",

        # Qt 6.5 debug build
        # [758352:758352:0315/212511.747791:WARNING:render_widget_host_impl.cc(280)]
        # Input request on unbound interface
        "Input request on unbound interface",

        # Qt 6.5 debug build
        # [1408271:1408418:0317/201633.360945:ERROR:http_cache_transaction.cc(3622)]
        # ReadData failed: 0
        "ReadData failed: 0",

        # Qt 6.{4,5}, possibly relates to a lifecycle mismatch between Qt and
        # Chromium but no issues have been concretely linked to it yet.
        # [5464:5464:0318/024215.821650:ERROR:interface_endpoint_client.cc(687)] Message 6 rejected by interface blink.mojom.WidgetHost
        # [5718:5718:0318/031330.803863:ERROR:interface_endpoint_client.cc(687)] Message 3 rejected by interface blink.mojom.Widget
        "Message * rejected by interface blink.mojom.Widget*",

        # GitHub Actions, Qt 6.6
        # [9895:9983:0904/043039.500565:ERROR:gpu_memory_buffer_support_x11.cc(49)]
        # dri3 extension not supported.
        "dri3 extension not supported.",

        # Qt 6.7 debug build
        # [44513:44717:0325/173456.146759:WARNING:render_message_filter.cc(144)]
        # Could not find tid
        "Could not find tid",

        # [127693:127748:0325/230155.835421:WARNING:discardable_shared_memory_manager.cc(438)]
        # Some MojoDiscardableSharedMemoryManagerImpls are still alive. They
        # will be leaked.
        "Some MojoDiscardableSharedMemoryManagerImpls are still alive. They will be leaked.",

        # Qt 6.7 on GitHub Actions
        # [3456:5752:1111/103609.929:ERROR:block_files.cc(443)] Failed to open
        # C:\Users\RUNNER~1\AppData\Local\Temp\qutebrowser-basedir-ruvn1lys\data\webengine\DawnCache\data_0
        "Failed to open *webengine*Dawn*Cache*data_*",

        # Qt 6.8 on GitHub Actions
        # [7072:3412:1209/220659.527:ERROR:simple_index_file.cc(322)] Failed to
        # write the temporary index file
        "Failed to write the temporary index file",

        # Qt 6.9 Beta 3 on GitHub Actions
        # [978:1041:0311/070551.759339:ERROR:bus.cc(407)]
        "Failed to connect to the bus: Failed to connect to socket /run/dbus/system_bus_socket: No such file or directory",

        # Qt 6.9 on GitHub Actions with Windows Server 2025
        # [4348:7828:0605/123815.402:ERROR:shared_image_manager.cc(356)]
        "SharedImageManager::ProduceMemory: Trying to Produce a Memory representation from a non-existent mailbox.",
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
        self._instance_id = next(instance_counter)
        self._run_counter = itertools.count()
        self._screenshot_counters = collections.defaultdict(itertools.count)

    def _process_line(self, log_line):
        """Check if the line matches any initial lines we're interested in."""
        start_okay_message = (
            "load status for <qutebrowser.browser.* tab_id=0 "
            "url='about:blank'>: LoadStatus.success")

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
              testutils.pattern_match(pattern=start_okay_message,
                                      value=log_line.message)):
            log_line.waited_for = True
            self.ready.emit()
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
        strace = self.request.config.getoption('--qute-strace-subprocs')
        if hasattr(sys, 'frozen'):
            if profile or strace:
                raise RuntimeError("Can't profile/strace with sys.frozen!")
            executable = str(pathlib.Path(sys.executable).parent / 'qutebrowser')
            args = []
        else:
            if strace:
                executable = 'strace'
                args = [
                    "-o",
                    "qb-strace",
                    "--output-separately",  # create .PID files
                    "--write=2",  # dump full stderr data (qb JSON logs)
                    sys.executable,
                ]
            else:
                executable = sys.executable
                args = []

            if profile:
                profile_dir = pathlib.Path.cwd() / 'prof'
                profile_id = '{}_{}'.format(self._instance_id,
                                            next(self._run_counter))
                profile_file = profile_dir / '{}.pstats'.format(profile_id)
                profile_dir.mkdir(exist_ok=True)
                args += [str(pathlib.Path('scripts') / 'dev' / 'run_profile.py'),
                        '--profile-tool', 'none',
                        '--profile-file', str(profile_file)]
            else:
                args += ['-bb', '-m', 'qutebrowser']
        return executable, args

    def _default_args(self):
        backend = 'webengine' if self.request.config.webengine else 'webkit'
        args = ['--debug', '--no-err-windows', '--temp-basedir',
                '--json-logging', '--loglevel', 'vdebug',
                '--backend', backend,
                '--debug-flag', 'no-sql-history',
                '--debug-flag', 'werror',
                '--debug-flag', 'test-notification-service',
                '--debug-flag', 'caret',
                '--qt-flag', 'disable-features=PaintHoldingCrossOrigin',
                '--qt-arg', 'geometry', '800x600+0+0']

        if self.request.config.webengine:
            if testutils.disable_seccomp_bpf_sandbox():
                args += testutils.DISABLE_SECCOMP_BPF_ARGS
            if testutils.use_software_rendering():
                args += testutils.SOFTWARE_RENDERING_ARGS

        args.append('about:blank')
        return args

    def path_to_url(self, path, *, port=None, https=False):
        """Get a URL based on a filename for the localhost webserver.

        URLs like about:... and qute:... are handled specially and returned
        verbatim.
        """
        special_schemes = ['about:', 'qute:', 'chrome:', 'view-source:',
                           'data:', 'http:', 'https:', 'file:']
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
            point = 'Py*.QtCore.QPoint(*, *)'  # not counting 0/0 here
        elif x == '0' and y == '0':
            point = 'Py*.QtCore.QPoint()'
        else:
            point = 'Py*.QtCore.QPoint({}, {})'.format(x, y)
        self.wait_for(category='webview',
                      message='Scroll position changed to ' + point)

    def wait_for(self, timeout=None, **kwargs):
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
        self.send_cmd(':clear-messages')
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
            if call.failed:
                self._take_x11_screenshot_of_failed_test()
            if call.failed or hasattr(call, 'wasxfail') or call.skipped:
                super().after_test()
                return

        try:
            if bad_msgs:
                text = 'Logged unexpected errors:\n\n' + '\n'.join(
                    str(e) for e in bad_msgs)
                pytest.fail(text, pytrace=False)
            else:
                self._maybe_skip()
        finally:
            super().after_test()

    def _wait_for_ipc(self):
        """Wait for an IPC message to arrive."""
        self.wait_for(category='ipc', module='ipc', function='on_ready_read',
                      message='Read from socket *')

    @contextlib.contextmanager
    def disable_capturing(self):
        capmanager = self.request.config.pluginmanager.getplugin("capturemanager")
        with capmanager.global_and_fixture_disabled():
            yield

    def _after_start(self):
        """Wait before continuing if requested, e.g. for debugger attachment."""
        delay = self.request.config.getoption('--qute-delay-start')
        if delay:
            with self.disable_capturing():
                print(f"- waiting {delay}ms for quteprocess "
                      f"(PID: {self.proc.processId()})...")
            time.sleep(delay / 1000)

    def send_ipc(self, commands, target_arg=''):
        """Send a raw command to the running IPC socket."""
        delay = self.request.config.getoption('--qute-delay')
        time.sleep(delay / 1000)

        assert self._ipc_socket is not None
        ipc.send_to_running_instance(self._ipc_socket, commands, target_arg)

        try:
            self._wait_for_ipc()
        except testprocess.WaitForTimeout:
            # Sometimes IPC messages seem to get lost on Windows CI?
            # Retry a second time as this shouldn't make tests fail.
            ipc.send_to_running_instance(self._ipc_socket, commands,
                                         target_arg)
            self._wait_for_ipc()

    def start(self, *args, **kwargs):
        try:
            super().start(*args, **kwargs)
        except testprocess.ProcessExited:
            is_dl_inconsistency = str(self.captured_log[-1]).endswith(
                "_dl_allocate_tls_init: Assertion "
                "`listp->slotinfo[cnt].gen <= GL(dl_tls_generation)' failed!")
            if testutils.ON_CI and is_dl_inconsistency:
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
        __tracebackhide__ = lambda e: e.errisinstance(testprocess.WaitForTimeout)
        summary = command
        if count is not None:
            summary += ' (count {})'.format(count)
        self.log_summary(summary)

        if escape:
            command = command.replace('\\', r'\\')

        if count is not None:
            command = ':cmd-run-with-count {} {}'.format(count,
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
            if testutils.ON_CI:
                timeout = 15000
            else:
                timeout = 5000

        qurl = QUrl(url)
        if not qurl.isValid():
            raise ValueError("Invalid URL {}: {}".format(url,
                                                         qurl.errorString()))

        # We really need the same representation that the webview uses in
        # its __repr__
        url = utils.elide(qurl.toDisplayString(QUrl.ComponentFormattingOption.EncodeUnicode), 100)
        assert url

        pattern = re.compile(
            r"(load status for <qutebrowser\.browser\..* "
            r"tab_id=\d+ url='{url}/?'>: LoadStatus\.{load_status}|fetch: "
            r"Py.*\.QtCore\.QUrl\('{url}'\) -> .*)".format(
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

    def get_session(self, flags="--with-private"):
        """Save the session and get the parsed session data."""
        with tempfile.TemporaryDirectory() as tdir:
            session = pathlib.Path(tdir) / 'session.yml'
            self.send_cmd(f':session-save {flags} "{session}"')
            self.wait_for(category='message', loglevel=logging.INFO,
                          message=f'Saved session {session}.')
            data = session.read_text(encoding='utf-8')

        self._log('\nCurrent session data:\n' + data)
        return utils.yaml_load(data)

    def get_content(self, plain=True):
        """Get the contents of the current page."""
        with tempfile.TemporaryDirectory() as tdir:
            path = pathlib.Path(tdir) / 'page'

            if plain:
                self.send_cmd(':debug-dump-page --plain "{}"'.format(path))
            else:
                self.send_cmd(':debug-dump-page "{}"'.format(path))

            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Dumped page to {}.'.format(path))

            return path.read_text(encoding='utf-8')

    def get_screenshot(
            self,
            *,
            probe_pos: QPoint = None,
            probe_color: QColor = testutils.Color(0, 0, 0),
    ) -> QImage:
        """Get a screenshot of the current page.

        Arguments:
            probe_pos: If given, only continue if the pixel at the given
                       position isn't black (or whatever is specified by probe_color).
        """
        for _ in range(5):
            tmp_path = self.request.getfixturevalue('tmp_path')
            counter = self._screenshot_counters[self.request.node.nodeid]

            path = tmp_path / f'screenshot-{next(counter)}.png'
            self.send_cmd(f':screenshot {path}')

            screenshot_msg = f'Screenshot saved to {path}'
            self.wait_for(message=screenshot_msg)
            print(screenshot_msg)

            img = QImage(str(path))
            assert not img.isNull()

            if probe_pos is None:
                return img

            probed_color = testutils.Color(img.pixelColor(probe_pos))
            if probed_color == probe_color:
                return img

            # Rendering might not be completed yet...
            time.sleep(0.5)

        # Using assert again for pytest introspection
        assert probed_color == probe_color, "Color probing failed, values on last try:"
        raise utils.Unreachable()

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

    def compare_session(self, expected, *, flags="--with-private"):
        """Compare the current sessions against the given template.

        partial_compare is used, which means only the keys/values listed will
        be compared.
        """
        __tracebackhide__ = lambda e: e.errisinstance(pytest.fail.Exception)
        data = self.get_session(flags=flags)
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

    def _take_x11_screenshot_of_failed_test(self):
        fixture = self.request.getfixturevalue('take_x11_screenshot')
        fixture()


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


@pytest.fixture
def screenshot_dir(request, tmp_path_factory):
    """Return the path of a directory to save e2e screenshots in."""
    path = tmp_path_factory.getbasetemp()
    if "PYTEST_XDIST_WORKER" in os.environ:
        # If we are running under xdist remove the per-worker directory
        # (like "popen-gw0") so the user doesn't have to search through
        # multiple folders for the screenshot they are looking for.
        path = path.parent
    path /= "pytest-screenshots"
    path.mkdir(exist_ok=True)
    return path


@pytest.fixture
def take_x11_screenshot(request, screenshot_dir, record_property, xvfb):
    """Take a screenshot of the current pytest-xvfb display.

    Screenshots are saved to the location of the `screenshot_dir` fixture.
    """
    def doit():
        if not xvfb:
            # Likely we are being run with --no-xvfb
            return

        img = grab(xdisplay=f":{xvfb.display}")
        fpath = screenshot_dir / f"{request.node.name}.png"
        img.save(fpath)

        record_property("screenshot", str(fpath))
    return doit


@pytest.fixture(scope='module')
def quteproc_process(qapp, server, request):
    """Fixture for qutebrowser process which is started once per file."""
    # Passing request so it has an initial config
    proc = QuteProc(request)
    proc.start()
    yield proc
    proc.terminate()


@pytest.fixture
def quteproc(quteproc_process, server, request, take_x11_screenshot):
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
