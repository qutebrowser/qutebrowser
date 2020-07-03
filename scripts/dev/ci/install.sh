#!/bin/bash
# vim: ft=sh fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

set -e

pip_install() {
    python -m pip install "$@"
}

testenv=$1

[[ $testenv == eslint ]] && npm install -g eslint

pip_install -U pip
pip_install -U -r misc/requirements/requirements-tox.txt

[[ $testenv == docs ]] && sudo apt install --no-install-recommends asciidoc
[[ $testenv == *-cov ]] && pip_install -U -r misc/requirements/requirements-codecov.txt
exit 0
