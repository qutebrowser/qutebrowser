# Copyright 2021-2022 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Rewrite PyQt enums based on rewrite_find_enums.py output."""


import pathlib
import sys
import re

script_path = pathlib.Path(__file__).parent

replacements = []
with (script_path / 'enums.txt').open(encoding="utf-8") as f:
    for line in f:
        orig, replacement = line.split()
        orig_re = re.compile(re.escape(orig) + r'(?=\W)')
        replacements.append((orig_re, replacement))


for filename in sys.argv[1:]:
    path = pathlib.Path(filename)
    if path.suffix != '.py':
        continue
    content = path.read_text(encoding="utf-8")
    print(filename)
    for orig_re, replacement in replacements:
        content = orig_re.sub(replacement, content)
    path.write_text(content, encoding="utf-8")
