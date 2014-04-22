#!/bin/bash

# Inspired by herbstluftwm.

cat > AUTHORS  <<EOF
Contributors, sorted by the number of commits in descending order:

$(git log   --format="%aN" | sort | uniq -c | sort -nr | sed 's/^[ ]*[^ ]*[ ]*//')
EOF
