#!/bin/sh
#
#  Find all possible core files under current directory. Attempt
#  to determine exe using file(1) and dump stack trace with gdb.
#
say () { printf "\033[91m%s\033[39m\n" "$@" >&2; }
die () { say "$@"; exit 1; }

find . -name *.core -o -name core | while read -r line; do
    d=$(dirname $line)
    f=$(basename $line)
    exe=$(file $line | sed "s/.*from '\([^ \t]*\).*'.*/\1/")
    ( cd $d &&
      test -x $exe || die "Failed to find executable at $exe" &&
      say "Found corefile for $exe" &&
      gdb --batch --quiet -ex "thread apply all bt full" $exe $f
    )
done
