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

"""Test starting qutebrowser with various commandline arguments."""

import pytest


@pytest.mark.linux
def test_no_config(tmpdir, quteproc_new):
    """Test starting with -c "".

    We can't run --basedir or --temp-basedir to reproduce this, so we mess with
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

    args = ['--debug', '--no-err-windows', '-c', '', 'about:blank']
    quteproc_new.start(args, env=env)
    quteproc_new.send_cmd(':quit')
    quteproc_new.wait_for_quit()
