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

import pytest

BASE_ARGS = ['--debug', '--json-logging', '--no-err-windows', 'about:blank']


@pytest.fixture
def temp_basedir_env(tmpdir):
    """Return a dict of environment variables that fakes --temp-basedir.

    We can't run --basedir or --temp-basedir for some tests, so we mess with
    XDG_*_DIR to get things relocated.
    """
    data_dir = tmpdir / 'data'
    config_dir = tmpdir / 'config'
    runtime_dir = tmpdir / 'runtime'
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
def test_no_config(temp_basedir_env, quteproc_new):
    """Test starting with -c ""."""
    args = ['-c', ''] + BASE_ARGS
    quteproc_new.start(args, env=temp_basedir_env)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.linux
def test_no_cache(temp_basedir_env, quteproc_new):
    """Test starting with --cachedir=""."""
    args = ['--cachedir='] + BASE_ARGS
    quteproc_new.start(args, env=temp_basedir_env)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()


@pytest.mark.linux
def test_ascii_locale(httpbin, tmpdir, quteproc_new):
    """Test downloads with LC_ALL=C set.

    https://github.com/The-Compiler/qutebrowser/issues/908
    """
    args = ['--temp-basedir'] + BASE_ARGS
    quteproc_new.start(args, env={'LC_ALL': 'C'})
    quteproc_new.set_setting('storage', 'download-directory', str(tmpdir))
    quteproc_new.set_setting('storage', 'prompt-download-directory', 'false')
    url = 'http://localhost:{port}/data/downloads/ä-issue908.bin'.format(
        port=httpbin.port)
    quteproc_new.send_cmd(':download {}'.format(url))
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()

    assert len(tmpdir.listdir()) == 1
    assert (tmpdir / '?-issue908.bin').exists()


def test_no_loglines(quteproc_new):
    """Test qute:log with --loglines=0."""
    quteproc_new.start(args=['--temp-basedir', '--loglines=0'] + BASE_ARGS)
    quteproc_new.open_path('qute:log')
    assert quteproc_new.get_content() == 'Log output was disabled.'
