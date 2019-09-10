#!/bin/bash
# vim: ft=sh fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

# Stolen from https://github.com/travis-ci/travis-build/blob/master/lib/travis/build/templates/header.sh
# and adjusted to use ((...))
travis_retry() {
    local ANSI_RED='\033[31;1m'
    local ANSI_RESET='\033[0m'
    local result=0
    local count=1
    while (( count < 3 )); do
        if (( result != 0 )); then
            echo -e "\\n${ANSI_RED}The command \"$*\" failed. Retrying, $count of 3.${ANSI_RESET}\\n" >&2
        fi
        "$@"
        result=$?
        (( result == 0 )) && break
        count=$(( count + 1 ))
        sleep 1
    done

    if (( count > 3 )); then
        echo -e "\\n${ANSI_RED}The command \"$*\" failed 3 times.${ANSI_RESET}\\n" >&2
    fi

    return $result
}

pip_install() {
    travis_retry python3 -m pip install "$@"
}

npm_install() {
    # Make sure npm is up-to-date first
    travis_retry npm install -g npm
    travis_retry npm install -g "$@"
}

set -e

if [[ -n $DOCKER ]]; then
    exit 0
elif [[ $TRAVIS_OS_NAME == osx ]]; then
    brew update
    brew upgrade python
fi

case $TESTENV in
    eslint)
        npm_install eslint
        ;;
    shellcheck)
        ;;
    *)
        pip_install -U pip
        pip_install -U -r misc/requirements/requirements-tox.txt
        if [[ $TESTENV == *-cov ]]; then
            pip_install -U -r misc/requirements/requirements-codecov.txt
        fi
        ;;
esac
