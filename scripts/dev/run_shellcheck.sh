#!/bin/bash

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


set -e

script_list=$(mktemp)
find scripts/ -name '*.sh' > "$script_list"
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
