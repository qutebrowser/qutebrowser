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

"""Test starting qutebrowser with special arguments/environments."""

import sys
import logging
import re

import pytest

from PyQt5.QtCore import QProcess

from end2end.fixtures import quteprocess, testprocess


def _base_args(config):
    """Get the arguments to pass with every invocation."""
    args = ['--debug', '--json-logging', '--no-err-windows']
    if config.webengine:
        args += ['--backend', 'webengine']
    else:
        args += ['--backend', 'webkit']
    args.append('about:blank')
    return args


@pytest.fixture
def temp_basedir_env(tmpdir, short_tmpdir):
    """Return a dict of environment variables that fakes --temp-basedir.

    We can't run --basedir or --temp-basedir for some tests, so we mess with
    XDG_*_DIR to get things relocated.
    """
    data_dir = tmpdir / 'data'
    config_dir = tmpdir / 'config'
    runtime_dir = short_tmpdir / 'rt'
    cache_dir = tmpdir / 'cache'

    runtime_dir.ensure(dir=True)
    runtime_dir.chmod(0o700)

    (data_dir / 'qutebrowser' / 'state').write_text(
        '[general]\nquickstart-done = 1', encoding='utf-8', ensure=True)

    env = {
        'XDG_DATA_HOME': str(data_dir),
        'XDG_CONFIG_HOME': str(config_dir),
        'XDG_RUNTIME_DIR': str(runtime_dir),
        'XDG_CACHE_HOME': str(cache_dir),
    }
    return env


@pytest.mark.linux
def test_no_config(request, temp_basedir_env, quteproc_new):
    """Test starting with -c ""."""
    args = ['-c', ''] + _base_args(request.config)
    quteproc_new.start(args, env=temp_basedir_env)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.linux
def test_no_cache(request, temp_basedir_env, quteproc_new):
    """Test starting with --cachedir=""."""
    args = ['--cachedir='] + _base_args(request.config)
    quteproc_new.start(args, env=temp_basedir_env)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.linux
def test_ascii_locale(request, httpbin, tmpdir, quteproc_new):
    """Test downloads with LC_ALL=C set.

    https://github.com/The-Compiler/qutebrowser/issues/908
    https://github.com/The-Compiler/qutebrowser/issues/1726
    """
    if request.config.webengine:
        pytest.skip("Downloads are not implemented with QtWebEngine yet")
    args = ['--temp-basedir'] + _base_args(request.config)
    quteproc_new.start(args, env={'LC_ALL': 'C'})
    quteproc_new.set_setting('storage', 'download-directory', str(tmpdir))

    # Test a normal download
    quteproc_new.set_setting('storage', 'prompt-download-directory', 'false')
    url = 'http://localhost:{port}/data/downloads/ä-issue908.bin'.format(
        port=httpbin.port)
    quteproc_new.send_cmd(':download {}'.format(url))
    quteproc_new.wait_for(category='downloads',
                          message='Download ?-issue908.bin finished')

    # Test :prompt-open-download
    quteproc_new.set_setting('storage', 'prompt-download-directory', 'true')
    quteproc_new.send_cmd(':download {}'.format(url))
    quteproc_new.send_cmd(':prompt-open-download "{}" -c pass'
                          .format(sys.executable))
    quteproc_new.wait_for(category='downloads',
                          message='Download ä-issue908.bin finished')
    quteproc_new.wait_for(category='downloads',
                          message='Opening * with [*python*]')

    assert len(tmpdir.listdir()) == 1
    assert (tmpdir / '?-issue908.bin').exists()


@pytest.mark.linux
def test_misconfigured_user_dirs(request, httpbin, temp_basedir_env,
                                 tmpdir, quteproc_new):
    """Test downloads with a misconfigured XDG_DOWNLOAD_DIR.

    https://github.com/The-Compiler/qutebrowser/issues/866
    https://github.com/The-Compiler/qutebrowser/issues/1269
    """
    if request.config.webengine:
        pytest.skip("Downloads are not implemented with QtWebEngine yet")

    home = tmpdir / 'home'
    home.ensure(dir=True)
    temp_basedir_env['HOME'] = str(home)

    assert temp_basedir_env['XDG_CONFIG_HOME'] == tmpdir / 'config'
    (tmpdir / 'config' / 'user-dirs.dirs').write('XDG_DOWNLOAD_DIR="relative"',
                                                 ensure=True)

    quteproc_new.start(_base_args(request.config), env=temp_basedir_env)

    quteproc_new.set_setting('storage', 'prompt-download-directory', 'false')
    url = 'http://localhost:{port}/data/downloads/download.bin'.format(
        port=httpbin.port)
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
    """Test qute:log with --loglines=0."""
    if request.config.webengine:
        pytest.skip("qute:log is not implemented with QtWebEngine yet")
    quteproc_new.start(args=['--temp-basedir', '--loglines=0'] +
                       _base_args(request.config))
    quteproc_new.open_path('qute:log')
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


def test_version(request):
    """Test invocation with --version argument."""
    args = ['--version'] + _base_args(request.config)
    # can't use quteproc_new here because it's confused by
    # early process termination
    proc = quteprocess.QuteProc(request)
    proc.proc.setProcessChannelMode(QProcess.SeparateChannels)

    try:
        proc.start(args)
        proc.wait_for_quit()
    except testprocess.ProcessExited:
        assert proc.proc.exitStatus() == QProcess.NormalExit
    else:
        pytest.fail("Process did not exit!")

    output = bytes(proc.proc.readAllStandardOutput()).decode('utf-8')

    assert re.search(r'^qutebrowser\s+v\d+(\.\d+)', output) is not None
