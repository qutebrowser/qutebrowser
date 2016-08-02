#!/bin/bash

# This script downloads the given release from GitHub so we can mirror it on
# qutebrowser.org.

tmpdir=$(mktemp -d)
oldpwd=$PWD

if [[ $# != 1 ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

cd "$tmpdir"
mkdir windows

base="https://github.com/The-Compiler/qutebrowser/releases/download/v$1"

wget "$base/qutebrowser-$1.tar.gz" || exit 1
wget "$base/qutebrowser-$1.tar.gz.asc" || exit 1
wget "$base/qutebrowser-$1.dmg" || exit 1
wget "$base/qutebrowser_${1}-1_all.deb" || exit 1

cd windows
wget "$base/qutebrowser-${1}-amd64.msi" || exit 1
wget "$base/qutebrowser-${1}-win32.msi" || exit 1
wget "$base/qutebrowser-${1}-windows-standalone-amd64.zip" || exit 1
wget "$base/qutebrowser-${1}-windows-standalone-win32.zip" || exit 1

dest="/srv/http/qutebrowser/releases/v$1"
cd "$oldpwd"
sudo mv "$tmpdir" "$dest"
sudo chown -R http:http "$dest"
