#!/usr/bin/python

"""Re-generate the AUTHORS file based on the commits made."""

import subprocess
from collections import Counter

commits = subprocess.check_output(['git', 'log', '--format=%aN'])
cnt = Counter(commits.decode('utf-8').splitlines())

with open('AUTHORS', 'w', newline='\n', encoding='utf-8') as f:
    f.write("Contributors, sorted by the number of commits in descending "
            "order:\n\n")
    for author in sorted(cnt, key=lambda k: cnt[k]):
        f.write(author)
    f.write('\n')
