#!/usr/bin/python

# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Re-generate the AUTHORS file based on the commits made."""

import subprocess
from collections import Counter

commits = subprocess.check_output(['git', 'log', '--format=%aN'])
cnt = Counter(commits.decode('utf-8').splitlines())

with open('doc/AUTHORS.asciidoc', 'w', newline='\n', encoding='utf-8') as f:
    f.write("Contributors, sorted by the number of commits in descending "
            "order:\n\n")
    for author in sorted(cnt, key=lambda k: cnt[k]):
        f.write('* ' + author)
    f.write('\n')
