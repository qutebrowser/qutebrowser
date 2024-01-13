# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
