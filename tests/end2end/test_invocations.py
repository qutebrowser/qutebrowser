# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test starting qutebrowser with special arguments/environments."""

import os
import signal
import configparser
import subprocess
import sys
import logging
import importlib
import re
import json
import platform
from contextlib import nullcontext as does_not_raise
from unittest.mock import ANY

import pytest
from qutebrowser.qt.core import QProcess, QPoint

from helpers import testutils
from qutebrowser.utils import qtutils, utils, version


ascii_locale = pytest.mark.skipif(sys.hexversion >= 0x03070000,
                                  reason="Python >= 3.7 doesn't force ASCII "
                                  "locale with LC_ALL=C")


# For some reason (some floating point rounding differences?), color values are
# slightly different (and wrong!) on ARM machines. We adjust our expected values
# accordingly, since we don't really care about the exact value, we just want to
# know that the underlying Chromium is respecting our preferences.
# FIXME what to do about 32-bit ARM?
IS_ARM = platform.machine() == 'aarch64'


def _base_args(config):
    """Get the arguments to pass with every invocation."""
    args = ['--debug', '--json-logging', '--no-err-windows']
    if config.webengine:
        args += ['--backend', 'webengine']
    else:
        args += ['--backend', 'webkit']

    if config.webengine:
        if testutils.disable_seccomp_bpf_sandbox():
            args += testutils.DISABLE_SECCOMP_BPF_ARGS
        if testutils.use_software_rendering():
            args += testutils.SOFTWARE_RENDERING_ARGS

    args.append('about:blank')
    return args


@pytest.fixture
def runtime_tmpdir(short_tmpdir):
    """A directory suitable for XDG_RUNTIME_DIR."""
    runtime_dir = short_tmpdir / 'rt'
    runtime_dir.ensure(dir=True)
    runtime_dir.chmod(0o700)
    return runtime_dir


@pytest.fixture
def temp_basedir_env(tmp_path, runtime_tmpdir):
    """Return a dict of environment variables that fakes --temp-basedir.

    We can't run --basedir or --temp-basedir for some tests, so we mess with
    XDG_*_DIR to get things relocated.
    """
    data_dir = tmp_path / 'data'
    config_dir = tmp_path / 'config'
    cache_dir = tmp_path / 'cache'

    lines = [
        '[general]',
        'quickstart-done = 1',
        'backend-warning-shown = 1',
        'webkit-warning-shown = 1',
    ]

    state_file = data_dir / 'qutebrowser' / 'state'
    state_file.parent.mkdir(parents=True)
    state_file.write_text('\n'.join(lines), encoding='utf-8')

    env = {
        'XDG_DATA_HOME': str(data_dir),
        'XDG_CONFIG_HOME': str(config_dir),
        'XDG_RUNTIME_DIR': str(runtime_tmpdir),
        'XDG_CACHE_HOME': str(cache_dir),
    }
    return env


@pytest.mark.linux
@ascii_locale
def test_downloads_with_ascii_locale(request, server, tmp_path, quteproc_new):
    """Test downloads with LC_ALL=C set.

    https://github.com/qutebrowser/qutebrowser/issues/908
    https://github.com/qutebrowser/qutebrowser/issues/1726
    """
    args = ['--temp-basedir'] + _base_args(request.config)
    quteproc_new.start(args, env={'LC_ALL': 'C'})
    quteproc_new.set_setting('downloads.location.directory', str(tmp_path))

    # Test a normal download
    quteproc_new.set_setting('downloads.location.prompt', 'false')
    url = 'http://localhost:{port}/data/downloads/ä-issue908.bin'.format(
        port=server.port)
    quteproc_new.send_cmd(':download {}'.format(url))
    quteproc_new.wait_for(category='downloads',
                          message='Download ?-issue908.bin finished')

    # Test :prompt-open-download
    quteproc_new.set_setting('downloads.location.prompt', 'true')
    quteproc_new.send_cmd(':download {}'.format(url))
    quteproc_new.send_cmd(':prompt-open-download "{}" -c pass'
                          .format(sys.executable))
    quteproc_new.wait_for(category='downloads',
                          message='Download ä-issue908.bin finished')
    quteproc_new.wait_for(category='misc',
                          message='Opening * with [*python*]')

    assert len(list(tmp_path.iterdir())) == 1
    assert (tmp_path / '?-issue908.bin').exists()


@pytest.mark.linux
@pytest.mark.parametrize('url', ['/föö.html', 'file:///föö.html'])
@ascii_locale
def test_open_with_ascii_locale(request, server, tmp_path, quteproc_new, url):
    """Test opening non-ascii URL with LC_ALL=C set.

    https://github.com/qutebrowser/qutebrowser/issues/1450
    """
    args = ['--temp-basedir'] + _base_args(request.config)
    quteproc_new.start(args, env={'LC_ALL': 'C'})
    quteproc_new.set_setting('url.auto_search', 'never')

    # Test opening a file whose name contains non-ascii characters.
    # No exception thrown means test success.
    quteproc_new.send_cmd(':open {}'.format(url))

    if not request.config.webengine:
        line = quteproc_new.wait_for(message="Error while loading *: Error "
                                     "opening /*: No such file or directory")
        line.expected = True

    quteproc_new.wait_for(message="load status for <* tab_id=* "
                          "url='*/f%C3%B6%C3%B6.html'>: LoadStatus.error")

    if request.config.webengine:
        line = quteproc_new.wait_for(message='Load error: ERR_FILE_NOT_FOUND')
        line.expected = True


@pytest.mark.linux
@ascii_locale
def test_open_command_line_with_ascii_locale(request, server, tmp_path,
                                             quteproc_new):
    """Test opening file via command line with a non-ascii name with LC_ALL=C.

    https://github.com/qutebrowser/qutebrowser/issues/1450
    """
    # The file does not actually have to exist because the relevant checks will
    # all be called. No exception thrown means test success.
    args = (['--temp-basedir'] + _base_args(request.config) +
            ['/home/user/föö.html'])
    quteproc_new.start(args, env={'LC_ALL': 'C'})

    if not request.config.webengine:
        line = quteproc_new.wait_for(message="Error while loading *: Error "
                                     "opening /*: No such file or directory")
        line.expected = True

    quteproc_new.wait_for(message="load status for <* tab_id=* "
                          "url='*/f*.html'>: LoadStatus.error")

    if request.config.webengine:
        line = quteproc_new.wait_for(message="Load error: ERR_FILE_NOT_FOUND")
        line.expected = True


@pytest.mark.linux
def test_misconfigured_user_dirs(request, server, temp_basedir_env,
                                 tmp_path, quteproc_new):
    """Test downloads with a misconfigured XDG_DOWNLOAD_DIR.

    https://github.com/qutebrowser/qutebrowser/issues/866
    https://github.com/qutebrowser/qutebrowser/issues/1269
    """
    home = tmp_path / 'home'
    home.mkdir()
    temp_basedir_env['HOME'] = str(home)
    config_userdir_dir = tmp_path / 'config'
    config_userdir_dir.mkdir(parents=True)
    config_userdir_file = tmp_path / 'config' / 'user-dirs.dirs'
    config_userdir_file.touch()

    assert temp_basedir_env['XDG_CONFIG_HOME'] == str(tmp_path / 'config')
    config_userdir_file.write_text('XDG_DOWNLOAD_DIR="relative"')

    quteproc_new.start(_base_args(request.config), env=temp_basedir_env)

    quteproc_new.set_setting('downloads.location.prompt', 'false')
    url = 'http://localhost:{port}/data/downloads/download.bin'.format(
        port=server.port)
    quteproc_new.send_cmd(':download {}'.format(url))
    line = quteproc_new.wait_for(
        loglevel=logging.ERROR, category='message',
        message='XDG_DOWNLOAD_DIR points to a relative path - please check '
                'your ~/.config/user-dirs.dirs. The download is saved in your '
                'home directory.')
    line.expected = True
    quteproc_new.wait_for(category='downloads',
                          message='Download download.bin finished')

    assert (home / 'download.bin').exists()


def test_no_loglines(request, quteproc_new):
    """Test qute://log with --loglines=0."""
    quteproc_new.start(args=['--temp-basedir', '--loglines=0'] +
                       _base_args(request.config))
    quteproc_new.open_path('qute://log')
    assert quteproc_new.get_content() == 'Log output was disabled.'


@pytest.mark.not_frozen
@pytest.mark.parametrize('level', ['1', '2'])
def test_optimize(request, quteproc_new, capfd, level):
    quteproc_new.start(args=['--temp-basedir'] + _base_args(request.config),
                       env={'PYTHONOPTIMIZE': level})
    if level == '2':
        msg = ("Running on optimize level higher than 1, unexpected behavior "
               "may occur.")
        line = quteproc_new.wait_for(message=msg)
        line.expected = True

    # Waiting for quit to make sure no other warning is emitted
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.not_frozen
@pytest.mark.flaky  # Fails sometimes with empty output...
def test_version(request):
    """Test invocation with --version argument."""
    args = ['-m', 'qutebrowser', '--version'] + _base_args(request.config)
    # can't use quteproc_new here because it's confused by
    # early process termination
    proc = QProcess()
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

    proc.start(sys.executable, args)
    ok = proc.waitForStarted(2000)
    assert ok
    ok = proc.waitForFinished(10000)

    stdout = bytes(proc.readAllStandardOutput()).decode('utf-8')
    print(stdout)
    stderr = bytes(proc.readAllStandardError()).decode('utf-8')
    print(stderr)

    assert ok
    assert proc.exitStatus() == QProcess.ExitStatus.NormalExit

    match = re.search(r'^qutebrowser\s+v\d+(\.\d+)', stdout, re.MULTILINE)
    assert match is not None


def test_qt_arg(request, quteproc_new, tmp_path):
    """Test --qt-arg."""
    args = (['--temp-basedir', '--qt-arg', 'stylesheet',
             str(tmp_path / 'does-not-exist')] + _base_args(request.config))
    quteproc_new.start(args)

    msg = 'QCss::Parser - Failed to load file  "*does-not-exist"'
    line = quteproc_new.wait_for(message=msg)
    line.expected = True

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.linux
def test_webengine_download_suffix(request, quteproc_new, tmp_path):
    """Make sure QtWebEngine does not add a suffix to downloads."""
    if not request.config.webengine:
        pytest.skip()

    download_dir = tmp_path / 'downloads'
    download_dir.mkdir()

    (tmp_path / 'user-dirs.dirs').write_text(
        'XDG_DOWNLOAD_DIR={}'.format(download_dir))
    env = {'XDG_CONFIG_HOME': str(tmp_path)}
    args = ['--temp-basedir'] + _base_args(request.config)
    quteproc_new.start(args, env=env)

    quteproc_new.set_setting('downloads.location.prompt', 'false')
    quteproc_new.set_setting('downloads.location.directory', str(download_dir))
    quteproc_new.open_path('data/downloads/download.bin', wait=False)
    quteproc_new.wait_for(category='downloads', message='Download * finished')
    quteproc_new.open_path('data/downloads/download.bin', wait=False)
    quteproc_new.wait_for(message='Entering mode KeyMode.yesno *')
    quteproc_new.send_cmd(':prompt-accept yes')
    quteproc_new.wait_for(category='downloads', message='Download * finished')

    files = list(download_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == 'download.bin'


def test_command_on_start(request, quteproc_new):
    """Make sure passing a command on start works.

    See https://github.com/qutebrowser/qutebrowser/issues/2408
    """
    args = (['--temp-basedir'] + _base_args(request.config) +
            [':quickmark-add https://www.example.com/ example'])
    quteproc_new.start(args)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.parametrize('python', ['python2', 'python3.6', 'python3.7'])
def test_launching_with_old_python(python):
    try:
        proc = subprocess.run(
            [python, '-m', 'qutebrowser', '--no-err-windows'],
            stderr=subprocess.PIPE,
            check=False)
    except FileNotFoundError:
        pytest.skip(f"{python} not found")
    assert proc.returncode == 1
    error = "At least Python 3.9 is required to run qutebrowser"
    assert proc.stderr.decode('ascii').startswith(error)


def test_initial_private_browsing(request, quteproc_new):
    """Make sure the initial window is private when the setting is set."""
    args = (_base_args(request.config) +
            ['--temp-basedir', '-s', 'content.private_browsing', 'true'])
    quteproc_new.start(args)

    quteproc_new.compare_session("""
        windows:
            - private: True
              tabs:
              - history:
                - url: about:blank
    """)

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


def test_loading_empty_session(tmp_path, request, quteproc_new):
    """Make sure loading an empty session opens a window."""
    session = tmp_path / 'session.yml'
    session.write_text('windows: []')

    args = _base_args(request.config) + ['--temp-basedir', '-r', str(session)]
    quteproc_new.start(args)

    quteproc_new.compare_session("""
        windows:
            - tabs:
              - history:
                - url: about:blank
    """)

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


def test_qute_settings_persistence(short_tmpdir, request, quteproc_new):
    """Make sure settings from qute://settings are persistent."""
    args = _base_args(request.config) + ['--basedir', str(short_tmpdir)]
    quteproc_new.start(args)
    quteproc_new.open_path('qute://settings/')
    quteproc_new.send_cmd(':jseval --world main '
                          'cset("search.ignore_case", "always")')
    quteproc_new.wait_for(message='No output or error')
    quteproc_new.wait_for(category='config',
                          message='Config option changed: '
                                  'search.ignore_case = always')

    assert quteproc_new.get_setting('search.ignore_case') == 'always'

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()

    quteproc_new.start(args)
    assert quteproc_new.get_setting('search.ignore_case') == 'always'

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.parametrize('value, expected', [
    # https://chromium-review.googlesource.com/c/chromium/src/+/2545444
    pytest.param(
        'always',
        'http://localhost:(port2)/headers-link/(port)',
        marks=pytest.mark.qt5_only,
    ),
    pytest.param(
        'always',
        'http://localhost:(port2)/',
        marks=pytest.mark.qt6_only,
    ),

    ('never', None),
    ('same-domain', 'http://localhost:(port2)/'),  # None with QtWebKit
])
def test_referrer(quteproc_new, server, server2, request, value, expected):
    """Check referrer settings."""
    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'content.headers.referer', value,
    ]
    quteproc_new.start(args)

    quteproc_new.open_path(f'headers-link/{server.port}', port=server2.port)
    quteproc_new.send_cmd(':click-element id link')
    quteproc_new.wait_for_load_finished('headers')

    content = quteproc_new.get_content()
    data = json.loads(content)
    print(data)
    headers = data['headers']

    if not request.config.webengine and value == 'same-domain':
        # With QtWebKit and same-domain, we don't send a referer at all.
        expected = None

    if expected is not None:
        for key, val in [('(port)', server.port), ('(port2)', server2.port)]:
            expected = expected.replace(key, str(val))

    assert headers.get('Referer') == expected


def test_preferred_colorscheme_unsupported(request, quteproc_new):
    """Test versions without preferred-color-scheme support."""
    if request.config.webengine:
        pytest.skip("preferred-color-scheme is supported")

    args = _base_args(request.config) + ['--temp-basedir']
    quteproc_new.start(args)
    quteproc_new.open_path('data/darkmode/prefers-color-scheme.html')
    content = quteproc_new.get_content()
    assert content == "Preference support missing."


@pytest.mark.qtwebkit_skip
@pytest.mark.parametrize('value', ["dark", "light", "auto", None])
def test_preferred_colorscheme(request, quteproc_new, value):
    """Make sure the the preferred colorscheme is set."""
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + ['--temp-basedir']
    if value is not None:
        args += ['-s', 'colors.webpage.preferred_color_scheme', value]
    quteproc_new.start(args)

    dark_text = "Dark preference detected."
    light_text = "Light preference detected."

    expected_values = {
        "dark": [dark_text],
        "light": [light_text],

        # Depends on the environment the test is running in.
        "auto": [dark_text, light_text],
        None: [dark_text, light_text],
    }
    xfail = False
    if qtutils.version_check('5.15.2', exact=True, compiled=False):
        # Test the WORKAROUND https://bugreports.qt.io/browse/QTBUG-89753
        # With that workaround, we should always get the light preference.
        for key in ["auto", None]:
            expected_values[key].remove(dark_text)
        xfail = value in ["auto", None]

    quteproc_new.open_path('data/darkmode/prefers-color-scheme.html')
    content = quteproc_new.get_content()
    assert content in expected_values[value]

    if xfail:
        # Unsatisfactory result, but expected based on a Qt bug.
        pytest.xfail("QTBUG-89753")


def test_preferred_colorscheme_with_dark_mode(
        request, quteproc_new, webengine_versions):
    """Test interaction between preferred-color-scheme and dark mode.

    We would actually expect a color of 34, 34, 34 and 'Dark preference detected.'.
    That was the behavior on Qt 5.14 and 5.15.0/.1.
    """
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'colors.webpage.preferred_color_scheme', 'dark',
        '-s', 'colors.webpage.darkmode.enabled', 'true',
        '-s', 'colors.webpage.darkmode.algorithm', 'brightness-rgb',
    ]
    if webengine_versions.webengine == utils.VersionNumber(6, 9):
        # WORKAROUND: For unknown reasons, dark mode colors are wrong with
        # Qt 6.9 + hardware rendering + Xvfb.
        args += testutils.SOFTWARE_RENDERING_ARGS
    quteproc_new.start(args)

    quteproc_new.open_path('data/darkmode/prefers-color-scheme.html')
    content = quteproc_new.get_content()

    if webengine_versions.webengine == utils.VersionNumber(5, 15, 2):
        # Our workaround breaks when dark mode is enabled...
        # Also, for some reason, dark mode doesn't work on that page either!
        expected_text = 'No preference detected.'
        expected_color = testutils.Color(0, 170, 0)  # green
        xfail = "QTBUG-89753"
    elif webengine_versions.webengine < utils.VersionNumber(6, 4):
        # https://bugs.chromium.org/p/chromium/issues/detail?id=1177973
        # No workaround known.
        expected_text = 'Light preference detected.'
        # light website color, inverted by darkmode
        if webengine_versions.webengine >= utils.VersionNumber(6):
            expected_color = (testutils.Color(148, 146, 148) if IS_ARM
                              else testutils.Color(144, 144, 144))
        else:
            expected_color = (testutils.Color(123, 125, 123) if IS_ARM
                              else testutils.Color(127, 127, 127))
        xfail = "Chromium bug 1177973"
    else:
        # Correct behavior on QtWebEngine 6.4 (and 5.14/5.15.0/5.15.1 in the past)
        expected_text = 'Dark preference detected.'
        expected_color = (testutils.Color(33, 32, 33) if IS_ARM
                          else testutils.Color(34, 34, 34))  # dark website color
        xfail = False

    pos = QPoint(0, 0)
    img = quteproc_new.get_screenshot(probe_pos=pos, probe_color=expected_color)
    color = testutils.Color(img.pixelColor(pos))

    assert content == expected_text
    assert color == expected_color
    if xfail:
        # We still do some checks, but we want to mark the test outcome as xfail.
        pytest.xfail(xfail)


@pytest.mark.qtwebkit_skip
@pytest.mark.parametrize('reason', [
    'Explicitly enabled',
    'Qt version changed',
    None,
])
def test_service_worker_workaround(
        request, server, quteproc_new, short_tmpdir, reason):
    """Make sure we remove the QtWebEngine Service Worker directory if configured."""
    args = _base_args(request.config) + ['--basedir', str(short_tmpdir)]
    if reason == 'Explicitly enabled':
        settings_args = ['-s', 'qt.workarounds.remove_service_workers', 'true']
    else:
        settings_args = []

    service_worker_dir = short_tmpdir / 'data' / 'webengine' / 'Service Worker'

    # First invocation: Create directory
    quteproc_new.start(args)
    quteproc_new.open_path('data/service-worker/index.html')
    server.wait_for(verb='GET', path='/data/service-worker/data.json')
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()
    assert service_worker_dir.exists()

    # Edit state file if needed
    state_file = short_tmpdir / 'data' / 'state'
    if reason == 'Qt version changed':
        parser = configparser.ConfigParser()
        parser.read(state_file)
        del parser['general']['qt_version']
        with state_file.open('w', encoding='utf-8') as f:
            parser.write(f)

    # Second invocation: Directory gets removed (if workaround enabled)
    quteproc_new.start(args + settings_args)
    if reason is not None:
        quteproc_new.wait_for(
            message=(f'Removing service workers at {service_worker_dir} '
                     f'(reason: {reason})'))

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()

    if reason is None:
        assert service_worker_dir.exists()
        quteproc_new.ensure_not_logged(message='Removing service workers at *')
    else:
        assert not service_worker_dir.exists()


@pytest.mark.parametrize('store', [True, False])
def test_cookies_store(quteproc_new, request, short_tmpdir, store):
    # Start test process
    args = _base_args(request.config) + [
        '--basedir', str(short_tmpdir),
        '-s', 'content.cookies.store', str(store),
    ]
    quteproc_new.start(args)

    # Set cookie and ensure it's set
    quteproc_new.open_path('cookies/set-custom?max_age=30', wait=False)
    quteproc_new.wait_for_load_finished('cookies')
    content = quteproc_new.get_content()
    data = json.loads(content)
    assert data == {'cookies': {'cookie': 'value'}}

    # Restart
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()
    quteproc_new.start(args)

    # Check cookies
    quteproc_new.open_path('cookies')
    content = quteproc_new.get_content()
    data = json.loads(content)
    expected_cookies = {'cookie': 'value'} if store else {}
    assert data == {'cookies': expected_cookies}

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


def test_permission_prompt_across_restart(quteproc_new, request, short_tmpdir):
    # Start test process
    args = _base_args(request.config) + [
        '--basedir', str(short_tmpdir),
        '-s', 'content.notifications.enabled', 'ask',
    ]
    quteproc_new.start(args)

    def notification_prompt(answer):
        quteproc_new.open_path('data/prompt/notifications.html')
        quteproc_new.send_cmd(':click-element id button')
        quteproc_new.wait_for(message='Asking question *')
        quteproc_new.send_cmd(f':prompt-accept {answer}')

    # Make sure we are prompted the first time we are opened in this basedir
    notification_prompt('yes')
    quteproc_new.wait_for_js('notification permission granted')

    # Restart with same basedir
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()
    quteproc_new.start(args)

    # We should be re-prompted in the new instance
    notification_prompt('no')

    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


# The 'colors' dictionaries in the parametrize decorator below have (QtWebEngine
# version, CPU architecture) as keys. Either of those (or both) can be None to
# say "on all other Qt versions" or "on all other CPU architectures".
@pytest.mark.parametrize('filename, algorithm, colors', [
    (
        'blank',
        'lightness-cielab',
        {
            (None, None): testutils.Color(18, 18, 18),
            (None, 'aarch64'): testutils.Color(16, 16, 16),
        }
    ),
    (
        'blank',
        'lightness-hsl',
        {
            ('5.15', None): testutils.Color(0, 0, 0),
            ('6.2', None): testutils.Color(0, 0, 0),
            # Qt 6.3+ (why #121212 rather than #000000?)
            (None, None): testutils.Color(18, 18, 18),
        }
    ),
    (
        'blank',
        'brightness-rgb',
        {
            ('5.15', None): testutils.Color(0, 0, 0),
            ('6.2', None): testutils.Color(0, 0, 0),
            # Qt 6.3+ (why #121212 rather than #000000?)
            (None, None): testutils.Color(18, 18, 18),
        }
    ),

    (
        'yellow',
        'lightness-cielab',
        {
            (None, None): testutils.Color(35, 34, 0),
            (None, 'aarch64'): testutils.Color(33, 32, 0),
        }
    ),
    (
        'yellow',
        'lightness-hsl',
        {
            (None, None): testutils.Color(215, 215, 0),
            (None, 'aarch64'): testutils.Color(214, 215, 0),
            ('5.15', None): testutils.Color(204, 204, 0),
            ('5.15', 'aarch64'): testutils.Color(206, 207, 0),
        },
    ),
    (
        'yellow',
        'brightness-rgb',
        {
            (None, None): testutils.Color(0, 0, 215),
            (None, 'aarch64'): testutils.Color(0, 0, 214),
            ('5.15', None): testutils.Color(0, 0, 204),
            ('5.15', 'aarch64'): testutils.Color(0, 0, 206),
        }
    ),
])
def test_dark_mode(webengine_versions, quteproc_new, request,
                   filename, algorithm, colors):
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'colors.webpage.darkmode.enabled', 'true',
        '-s', 'colors.webpage.darkmode.algorithm', algorithm,
    ]
    if webengine_versions.webengine == utils.VersionNumber(6, 9):
        # WORKAROUND: For unknown reasons, dark mode colors are wrong with
        # Qt 6.9 + hardware rendering + Xvfb.
        args += testutils.SOFTWARE_RENDERING_ARGS

    quteproc_new.start(args)
    minor_version = str(webengine_versions.webengine.strip_patch())

    arch = platform.machine()
    for key in [
        (minor_version, arch),
        (minor_version, None),
        (None, arch),
        (None, None),
    ]:
        if key in colors:
            expected = colors[key]
            break

    quteproc_new.open_path(f'data/darkmode/{filename}.html')

    # Position chosen by fair dice roll.
    # https://xkcd.com/221/
    quteproc_new.get_screenshot(
        probe_pos=QPoint(4, 4),
        probe_color=expected,
    )


@pytest.mark.parametrize("suffix", ["inline", "display"])
def test_dark_mode_mathml(webengine_versions, quteproc_new, request, qtbot, suffix):
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'colors.webpage.darkmode.enabled', 'true',
        '-s', 'colors.webpage.darkmode.algorithm', 'brightness-rgb',
    ]
    if webengine_versions.webengine == utils.VersionNumber(6, 9):
        # WORKAROUND: For unknown reasons, dark mode colors are wrong with
        # Qt 6.9 + hardware rendering + Xvfb.
        args += testutils.SOFTWARE_RENDERING_ARGS

    quteproc_new.start(args)

    quteproc_new.open_path(f'data/darkmode/mathml-{suffix}.html')
    quteproc_new.wait_for_js('Image loaded')

    # First make sure loading finished by looking outside of the image
    if webengine_versions.webengine >= utils.VersionNumber(6):
        expected = testutils.Color(0, 0, 214) if IS_ARM else testutils.Color(0, 0, 215)
    else:
        expected = testutils.Color(0, 0, 206) if IS_ARM else testutils.Color(0, 0, 204)

    quteproc_new.get_screenshot(
        probe_pos=QPoint(105, 0),
        probe_color=expected,
    )

    # Then get the actual formula color, probing again in case it's not displayed yet...
    quteproc_new.get_screenshot(
        probe_pos=QPoint(4, 4),
        probe_color=testutils.Color(255, 255, 255),
    )


@pytest.mark.parametrize('value, preference', [
    ('true', 'Reduced motion'),
    ('false', 'No'),
])
@pytest.mark.skipif(
    utils.is_windows,
    reason="Outcome on Windows depends on system settings",
)
def test_prefers_reduced_motion(quteproc_new, request, value, preference):
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'content.prefers_reduced_motion', value,
    ]
    quteproc_new.start(args)

    quteproc_new.open_path('data/prefers_reduced_motion.html')
    content = quteproc_new.get_content()
    assert content == f"{preference} preference detected."


def test_unavailable_backend(request, quteproc_new):
    """Test starting with a backend which isn't available.

    If we use --qute-bdd-webengine, we test with QtWebKit here; otherwise we test with
    QtWebEngine. If both are available, the test is skipped.

    This ensures that we don't accidentally use backend-specific code before checking
    that the chosen backend is actually available - i.e., that the error message is
    properly printed, rather than an unhandled exception.
    """
    qtwe_module = "qutebrowser.qt.webenginewidgets"
    qtwk_module = "qutebrowser.qt.webkitwidgets"
    # Note we want to try the *opposite* backend here.
    if request.config.webengine:
        pytest.importorskip(qtwe_module)
        module = qtwk_module
        backend = 'webkit'
    else:
        pytest.importorskip(qtwk_module)
        module = qtwe_module
        backend = 'webengine'

    try:
        importlib.import_module(module)
    except ImportError:
        pass
    else:
        pytest.skip(f"{module} is available")

    args = [
        '--debug', '--json-logging', '--no-err-windows',
        '--backend', backend,
        '--temp-basedir'
    ]
    quteproc_new.exit_expected = True
    quteproc_new.start(args)
    line = quteproc_new.wait_for(
        message=('*qutebrowser tried to start with the Qt* backend but failed '
                 'because * could not be imported.*'))
    line.expected = True


def test_json_logging_without_debug(request, quteproc_new, runtime_tmpdir):
    args = _base_args(request.config) + ['--temp-basedir', ':quit']
    args.remove('--debug')
    args.remove('about:blank')  # interferes with :quit at the end

    quteproc_new.exit_expected = True
    quteproc_new.start(args, env={'XDG_RUNTIME_DIR': str(runtime_tmpdir)})
    assert not quteproc_new.is_running()


@pytest.mark.qtwebkit_skip
@pytest.mark.parametrize(
    'sandboxing, has_namespaces, has_seccomp, has_yama, expected_result', [
        ('enable-all', True, True, True, "You are adequately sandboxed."),
        ('disable-seccomp-bpf', True, False, True, "You are NOT adequately sandboxed."),
        ('disable-all', False, False, False, "You are NOT adequately sandboxed."),
    ]
)
def test_sandboxing(
        request, quteproc_new, sandboxing,
        has_namespaces, has_seccomp, has_yama, expected_result,
):
    # https://github.com/qutebrowser/qutebrowser/issues/8424
    userns_restricted = testutils.is_userns_restricted()

    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")
    elif sandboxing == "enable-all" and testutils.disable_seccomp_bpf_sandbox():
        pytest.skip("Full sandboxing not supported")
    elif version.is_flatpak() or userns_restricted:
        # https://github.com/flathub/io.qt.qtwebengine.BaseApp/pull/66
        has_namespaces = False
        expected_result = "You are NOT adequately sandboxed."
        has_yama_non_broker = has_yama
    else:
        has_yama_non_broker = False

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'qt.chromium.sandboxing', sandboxing,
    ]
    quteproc_new.start(args)

    quteproc_new.open_url('chrome://sandbox')
    text = quteproc_new.get_content()
    print(text)

    not_found_msg = ("The webpage at chrome://sandbox/ might be temporarily down or "
                     "it may have moved permanently to a new web address.")
    if not_found_msg in text.split("\n"):
        line = quteproc_new.wait_for(message='Load error: ERR_INVALID_URL')
        line.expected = True
        pytest.skip("chrome://sandbox/ not supported")

    if len(text.split("\n")) == 1:
        # Try again, maybe the JS hasn't run yet?
        text = quteproc_new.get_content()
        print(text)

    bpf_text = "Seccomp-BPF sandbox"
    yama_text = "Ptrace Protection with Yama LSM"

    if not utils.is_windows:
        header, *lines, empty, result = text.split("\n")
        assert not empty

        expected_status = {
            "Layer 1 Sandbox": "Namespace" if has_namespaces else "None",

            "PID namespaces": "Yes" if has_namespaces else "No",
            "Network namespaces": "Yes" if has_namespaces else "No",

            bpf_text: "Yes" if has_seccomp else "No",
            f"{bpf_text} supports TSYNC": "Yes" if has_seccomp else "No",

            f"{yama_text} (Broker)": "Yes" if has_yama else "No",
            # pylint: disable-next=used-before-assignment
            f"{yama_text} (Non-broker)": "Yes" if has_yama_non_broker else "No",
        }

        assert header == "Sandbox Status"
        assert result == expected_result

        status = dict(line.split("\t") for line in lines)
        assert status == expected_status

    else:  # utils.is_windows
        # The sandbox page on Windows if different that Linux and macOS. It's
        # a lot more complex. There is a table up top with lots of columns and
        # a row per tab and helper process then a json object per row down
        # below with even more detail (which we ignore).
        # https://www.chromium.org/Home/chromium-security/articles/chrome-sandbox-diagnostics-for-windows/

        # We're not getting full coverage of the table and there doesn't seem
        # to be a simple summary like for linux. The "Sandbox" and "Lockdown"
        # column are probably the key ones.
        # We are looking at all the rows in the table for the sake of
        # completeness, but I expect there will always be just one row with a
        # renderer process in it for this test. If other helper processes pop
        # up we might want to exclude them.
        lines = text.split("\n")
        assert lines.pop(0) == "Sandbox Status"
        header = lines.pop(0).split("\t")
        rows = []
        current_line = lines.pop(0)
        while current_line.strip():
            if lines[0].startswith("\t"):
                # Continuation line. Not sure how to 100% identify them
                # but new rows should start with a process ID.
                current_line += lines.pop(0)
                continue

            columns = current_line.split("\t")
            assert len(header) == len(columns)
            rows.append(dict(zip(header, columns)))
            current_line = lines.pop(0)

        assert rows

        # I'm using has_namespaces as a proxy for "should be sandboxed" here,
        # which is a bit lazy but its either that or match on the text
        # "sandboxing" arg. The seccomp-bpf arg does nothing on windows, so
        # we only have the off and on states.
        for row in rows:
            assert row == {
                "Process": ANY,
                "Type": "Renderer",
                "Name": "",
                "Sandbox": "Renderer" if has_namespaces else "Not Sandboxed",
                "Lockdown": "Lockdown" if has_namespaces else "",
                "Integrity": ANY if has_namespaces else "",
                "Mitigations": ANY if has_namespaces else "",
                "Component Filter": ANY if has_namespaces else "",
                "Lowbox/AppContainer": "",
            }


@pytest.mark.not_frozen
def test_logfilter_arg_does_not_crash(request, quteproc_new):
    args = ['--temp-basedir', '--debug', '--logfilter', 'commands, init, ipc, webview']

    with does_not_raise():
        quteproc_new.start(args=args + _base_args(request.config))

    # Waiting for quit to make sure no other warning is emitted
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


def test_restart(request, quteproc_new):
    args = _base_args(request.config) + ['--temp-basedir']
    quteproc_new.start(args)
    quteproc_new.send_cmd(':restart')

    prefix = "New process PID: "
    line = quteproc_new.wait_for(message=f"{prefix}*")
    quteproc_new.wait_for_quit()

    assert line.message.startswith(prefix)
    pid = int(line.message.removeprefix(prefix))
    os.kill(pid, signal.SIGTERM)

    # This often hangs on Windows for unknown reasons
    if not utils.is_windows:
        try:
            # If the new process hangs, this will hang too.
            # Still better than just ignoring it, so we can fix it if something is broken.
            os.waitpid(pid, 0)  # pid, options... positional-only :(
        except (ChildProcessError, PermissionError):
            # Already gone. Even if not documented, Windows seems to raise PermissionError
            # here...
            pass
