# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""httpbin web server for integration tests.

This script gets called as a QProcess from integration/conftest.py.
"""

import sys
import os.path

from httpbin.core import app
import flask


@app.route('/data/<path:path>')
def send_data(path):
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        data_dir = os.path.join(basedir, 'integration', 'data')
    else:
        basedir = os.path.realpath(os.path.dirname(__file__))
        data_dir = os.path.join(basedir, 'data')
    print(basedir)
    return flask.send_from_directory(data_dir, path)


def main():
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        app.template_folder = os.path.join(basedir, 'integration', 'templates')
    app.run(port=int(sys.argv[1]), debug=True, use_reloader=False)


if __name__ == '__main__':
    main()
