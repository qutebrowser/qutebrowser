#!/bin/bash
# vim: ft=sh fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

script_list=$(mktemp)
find scripts/dev/ -name '*.sh' > "$script_list"
find misc/userscripts/ -type f -exec grep -lE '[/ ][bd]ash$|[/ ]sh$|[/ ]ksh$' {} + >> "$script_list"
mapfile -t scripts < "$script_list"
rm -f "$script_list"

if [[ $1 == --docker ]]; then
    shift 1
    docker run \
            -v "$PWD:/outside" \
            -w /outside \
            -t \
            koalaman/shellcheck:stable "$@" "${scripts[@]}"
else
    shellcheck --version
    shellcheck "$@" "${scripts[@]}"
fi
