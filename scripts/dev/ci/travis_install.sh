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
# and adjusted to use ((...))
travis_retry() {
    local ANSI_RED="\033[31;1m"
    local ANSI_RESET="\033[0m"
    local result=0
    local count=1
    while (( count < 3 )); do
        if (( result != 0 )); then
            echo -e "\n${ANSI_RED}The command \"$@\" failed. Retrying, $count of 3.${ANSI_RESET}\n" >&2
        fi
        "$@"
        result=$?
        (( result == 0 )) && break
        count=$(($count + 1))
        sleep 1
    done

    if (( count > 3 )); then
        echo -e "\n${ANSI_RED}The command \"$@\" failed 3 times.${ANSI_RESET}\n" >&2
    fi

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
    # this uses python2
    travis_retry sudo -H python -m pip install -r misc/requirements/requirements-$1.txt
}

npm_install() {
    # Make sure npm is up-to-date first
    travis_retry sudo npm install -g npm
    travis_retry sudo npm install -g "$@"
}

install_node() {
    curl -sL https://deb.nodesource.com/setup_4.x | sudo -E bash -
    apt_install nodejs
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
    curl -LO https://github.com/The-Compiler/homebrew-qt5-webkit/releases/download/v5.6.0-1/pyqt5-5.6.el_capitan.bottle.1.tar.gz
    curl -LO https://github.com/The-Compiler/homebrew-qt5-webkit/releases/download/v5.6.1_1-1/qt5-5.6.1-1.yosemite.bottle.1.tar.gz
    brew --version
    brew_install python3 {qt5,pyqt5}-*.bottle.1.tar.gz
    pip_install pip
    pip_install tox
    pip --version
    tox --version
    check_pyqt
    exit 0
fi

pyqt_pkgs="python3-pyqt5 python3-pyqt5.qtwebkit"

pip_install pip
pip_install tox

pip --version
tox --version

case $TESTENV in
    py34-cov)
        pip_install codecov
        apt_install xvfb $pyqt_pkgs libpython3.4-dev
        check_pyqt
        ;;
    pylint|vulture)
        apt_install $pyqt_pkgs libpython3.4-dev
        check_pyqt
        ;;
    flake8)
        apt_install libpython3.4-dev
        ;;
    docs)
        apt_install $pyqt_pkgs asciidoc libpython3.4-dev
        asciidoc --version
        check_pyqt
        ;;
    misc)
        apt_install libpython3.4-dev
        ;;
    pyroma|check-manifest)
        ;;
    eslint)
        install_node
        echo "node: $(node --version)"
        echo "npm: $(npm --version)"
        npm_install eslint
        echo "eslint: $(eslint --version)"
        ;;
    *)
        echo "Unknown testenv $TESTENV!" >&2
        exit 1
        ;;
esac
