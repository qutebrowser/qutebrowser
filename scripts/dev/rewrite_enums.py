import pathlib
import sys
import re

script_path = pathlib.Path(__file__).parent

replacements = []
with (script_path / 'enums.txt').open() as f:
    for line in f:
        orig, replacement = line.split()
        orig_re = re.compile(re.escape(orig) + r'(?=\W)')
        replacements.append((orig_re, replacement))


for filename in sys.argv[1:]:
    path = pathlib.Path(filename)
    if path.suffix != '.py':
        continue
    content = path.read_text()
    print(filename)
    for orig_re, replacement in replacements:
        content = orig_re.sub(replacement, content)
    path.write_text(content)
