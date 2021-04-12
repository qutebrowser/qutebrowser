# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Test starting qutebrowser with special arguments/environments."""

import configparser
import subprocess
import sys
import logging
import importlib
import re
import json

import pytest
from PyQt5.QtCore import QProcess, QPoint

from helpers import testutils
from qutebrowser.utils import qtutils, utils


ascii_locale = pytest.mark.skipif(sys.hexversion >= 0x03070000,
                                  reason="Python >= 3.7 doesn't force ASCII "
                                  "locale with LC_ALL=C")


def _base_args(config):
    """Get the arguments to pass with every invocation."""
    args = ['--debug', '--json-logging', '--no-err-windows']
    if config.webengine:
        args += ['--backend', 'webengine']
    else:
        args += ['--backend', 'webkit']

    if config.webengine:
        args += testutils.seccomp_args(qt_flag=True)

    args.append('about:blank')
    return args


@pytest.fixture
def temp_basedir_env(tmp_path, short_tmpdir):
    """Return a dict of environment variables that fakes --temp-basedir.

    We can't run --basedir or --temp-basedir for some tests, so we mess with
    XDG_*_DIR to get things relocated.
    """
    data_dir = tmp_path / 'data'
    config_dir = tmp_path / 'config'
    runtime_dir = short_tmpdir / 'rt'
    cache_dir = tmp_path / 'cache'

    runtime_dir.ensure(dir=True)
    runtime_dir.chmod(0o700)

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
        'XDG_RUNTIME_DIR': str(runtime_dir),
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
    config_userdir_dir = (tmp_path / 'config')
    config_userdir_dir.mkdir(parents=True)
    config_userdir_file = (tmp_path / 'config' / 'user-dirs.dirs')
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
    proc.setProcessChannelMode(QProcess.SeparateChannels)

    proc.start(sys.executable, args)
    ok = proc.waitForStarted(2000)
    assert ok
    ok = proc.waitForFinished(10000)

    stdout = bytes(proc.readAllStandardOutput()).decode('utf-8')
    print(stdout)
    stderr = bytes(proc.readAllStandardError()).decode('utf-8')
    print(stderr)

    assert ok
    assert proc.exitStatus() == QProcess.NormalExit

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
    args = (['--temp-basedir'] + _base_args(request.config))
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


@pytest.mark.parametrize('python', ['python2', 'python3.5'])
def test_launching_with_old_python(python):
    try:
        proc = subprocess.run(
            [python, '-m', 'qutebrowser', '--no-err-windows'],
            stderr=subprocess.PIPE,
            check=False)
    except FileNotFoundError:
        pytest.skip(f"{python} not found")
    assert proc.returncode == 1
    error = "At least Python 3.6.1 is required to run qutebrowser"
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
    ('always', 'http://localhost:(port2)/headers-link/(port)'),
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
    if request.config.webengine and qtutils.version_check('5.14'):
        pytest.skip("preferred-color-scheme is supported")

    args = _base_args(request.config) + ['--temp-basedir']
    quteproc_new.start(args)
    quteproc_new.open_path('data/darkmode/prefers-color-scheme.html')
    content = quteproc_new.get_content()
    assert content == "Preference support missing."


@pytest.mark.qtwebkit_skip
@testutils.qt514
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
    if not qtutils.version_check('5.15.2', compiled=False):
        # On older versions, "light" is not supported, so the result will depend on the
        # environment.
        expected_values["light"].append(dark_text)
    elif qtutils.version_check('5.15.2', exact=True, compiled=False):
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


@testutils.qt514
def test_preferred_colorscheme_with_dark_mode(
        request, quteproc_new, webengine_versions):
    """Test interaction between preferred-color-scheme and dark mode."""
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'colors.webpage.preferred_color_scheme', 'dark',
        '-s', 'colors.webpage.darkmode.enabled', 'true',
        '-s', 'colors.webpage.darkmode.algorithm', 'brightness-rgb',
    ]
    quteproc_new.start(args)

    quteproc_new.open_path('data/darkmode/prefers-color-scheme.html')
    content = quteproc_new.get_content()

    qtwe_version = webengine_versions.webengine
    xfail = None
    if utils.VersionNumber(5, 15, 3) <= qtwe_version <= utils.VersionNumber(6):
        # https://bugs.chromium.org/p/chromium/issues/detail?id=1177973
        # No workaround known.
        expected_text = 'Light preference detected.'
        # light website color, inverted by darkmode
        expected_color = testutils.Color(127, 127, 127)
        xfail = "Chromium bug 1177973"
    elif qtwe_version == utils.VersionNumber(5, 15, 2):
        # Our workaround breaks when dark mode is enabled...
        # Also, for some reason, dark mode doesn't work on that page either!
        expected_text = 'No preference detected.'
        expected_color = testutils.Color(0, 170, 0)  # green
        xfail = "QTBUG-89753"
    else:
        # Qt 5.14 and 5.15.0/.1 work correctly.
        # Hopefully, so does Qt 6.x in the future?
        expected_text = 'Dark preference detected.'
        expected_color = testutils.Color(34, 34, 34)  # dark website color
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
    pytest.param('Qt 5.14', marks=testutils.qt514),
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
    if reason == 'Qt 5.14':
        state_file.remove()
    elif reason == 'Qt version changed':
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


@testutils.qt513  # Qt 5.12 doesn't store cookies immediately
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


@pytest.mark.parametrize('filename, algorithm, colors', [
    (
        'blank',
        'lightness-cielab',
        {
            '5.15': testutils.Color(18, 18, 18),
            '5.14': testutils.Color(27, 27, 27),
            None: testutils.Color(0, 0, 0),
        }
    ),
    ('blank', 'lightness-hsl', {None: testutils.Color(0, 0, 0)}),
    ('blank', 'brightness-rgb', {None: testutils.Color(0, 0, 0)}),

    (
        'yellow',
        'lightness-cielab',
        {
            '5.15': testutils.Color(35, 34, 0),
            '5.14': testutils.Color(35, 34, 0),
            None: testutils.Color(204, 204, 0),
        }
    ),
    ('yellow', 'lightness-hsl', {None: testutils.Color(204, 204, 0)}),
    ('yellow', 'brightness-rgb', {None: testutils.Color(0, 0, 204)}),
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
    quteproc_new.start(args)

    ver = webengine_versions.webengine
    minor_version = str(ver.strip_patch())
    expected = colors.get(minor_version, colors[None])

    quteproc_new.open_path(f'data/darkmode/{filename}.html')

    # Position chosen by fair dice roll.
    # https://xkcd.com/221/
    quteproc_new.get_screenshot(
        probe_pos=QPoint(4, 4),
        probe_color=expected,
    )


def test_dark_mode_mathml(quteproc_new, request, qtbot):
    if not request.config.webengine:
        pytest.skip("Skipped with QtWebKit")

    args = _base_args(request.config) + [
        '--temp-basedir',
        '-s', 'colors.webpage.darkmode.enabled', 'true',
        '-s', 'colors.webpage.darkmode.algorithm', 'brightness-rgb',
    ]
    quteproc_new.start(args)

    quteproc_new.open_path('data/darkmode/mathml.html')
    quteproc_new.wait_for_js('Image loaded')

    # First make sure loading finished by looking outside of the image
    quteproc_new.get_screenshot(
        probe_pos=QPoint(105, 0),
        probe_color=testutils.Color(0, 0, 204),
    )

    # Then get the actual formula color, probing again in case it's not displayed yet...
    quteproc_new.get_screenshot(
        probe_pos=QPoint(4, 4),
        probe_color=testutils.Color(255, 255, 255),
    )


def test_unavailable_backend(request, quteproc_new):
    """Test starting with a backend which isn't available.

    If we use --qute-bdd-webengine, we test with QtWebKit here; otherwise we test with
    QtWebEngine. If both are available, the test is skipped.

    This ensures that we don't accidentally use backend-specific code before checking
    that the chosen backend is actually available - i.e., that the error message is
    properly printed, rather than an unhandled exception.
    """
    qtwe_module = "PyQt5.QtWebEngineWidgets"
    qtwk_module = "PyQt5.QtWebKitWidgets"
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
