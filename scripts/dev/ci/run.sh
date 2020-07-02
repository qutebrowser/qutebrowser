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
testenv=$1

args=()
# We only run unit tests on macOS because it's quite slow.
[[ $TRAVIS_OS_NAME == osx ]] && args+=('--qute-bdd-webengine' '--no-xvfb' 'tests/unit')

# GCC output in shellcheck for GitHub problem matchers
[[ $testenv == shellcheck ]] && args+=('-f' 'gcc')

# WORKAROUND for unknown crash inside swrast_dri.so
# See https://github.com/qutebrowser/qutebrowser/pull/4218#issuecomment-421931770
[[ $testenv == py36-pyqt59 ]] && export QT_QUICK_BACKEND=software

tox -e "$testenv" -- "${args[@]}"
