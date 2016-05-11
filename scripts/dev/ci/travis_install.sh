# vim: ft=sh fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
travis_retry() {
    local ANSI_RED="\033[31;1m"
    local ANSI_RESET="\033[0m"
    local result=0
    local count=1
    while [ $count -le 3 ]; do
        [ $result -ne 0 ] && {
            echo -e "\n${ANSI_RED}The command \"$@\" failed. Retrying, $count of 3.${ANSI_RESET}\n" >&2
        }
        "$@"
        result=$?
        [ $result -eq 0 ] && break
        count=$(($count + 1))
        sleep 1
    done

    [ $count -gt 3 ] && {
        echo -e "\n${ANSI_RED}The command \"$@\" failed 3 times.${ANSI_RESET}\n" >&2
    }

    return $result
}

apt_install() {
    travis_retry sudo apt-get -y -q update
    travis_retry sudo apt-get -y -q install --no-install-recommends "$@"
}

brew_install() {
    brew update
    brew install "$@"
}

pip_install() {
    # Make sure pip is up-to-date first
    travis_retry sudo -H python3 -m pip install -U pip
    travis_retry sudo -H python3 -m pip install -U "$@"
}

npm_install() {
    # Make sure npm is up-to-date first
    travis_retry sudo npm install -g npm
    travis_retry sudo npm install -g "$@"
}

check_pyqt() {
    python3 <<EOF
import sys
from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from sip import SIP_VERSION_STR

print("Python {}".format(sys.version))
print("PyQt5 {}".format(PYQT_VERSION_STR))
print("Qt5 {} (runtime {})".format(QT_VERSION_STR, qVersion()))
print("sip {}".format(SIP_VERSION_STR))
EOF
}

set -e

if [[ $DOCKER ]]; then
    exit 0
elif [[ $TRAVIS_OS_NAME == osx ]]; then
    # Disable App Nap
    defaults write NSGlobalDomain NSAppSleepDisabled -bool YES
    brew_install python3 pyqt5
    pip_install tox
    check_pyqt
    exit 0
fi

pyqt_pkgs="python3-pyqt5 python3-pyqt5.qtwebkit"

case $TESTENV in
    py34-cov)
        apt_install python3-pip xvfb $pyqt_pkgs
        pip_install tox codecov
        check_pyqt
        ;;
    pylint|vulture)
        apt_install python3-pip $pyqt_pkgs
        pip_install tox
        check_pyqt
        ;;
    flake8)
        # We need an up-to-date Python because of:
        # https://github.com/google/yapf/issues/46
        apt_install -t trusty-updates python3.4 python3-pip
        pip_install tox
        ;;
    docs)
        apt_install python3-pip $pyqt_pkgs asciidoc
        pip_install tox
        check_pyqt
        ;;
    misc|pyroma|check-manifest)
        pip_install tox
        ;;
    eslint)
        apt_install python3-pip npm nodejs nodejs-legacy
        pip_install tox
        npm_install eslint
        ;;
    *)
        echo "Unknown testenv $TESTENV!" >&2
        exit 1
        ;;
esac
