#!/bin/bash
#
#  Find all possible core files under current directory. Attempt
#  to determine exe using file(1) and dump stack trace with gdb.
#
say () { printf "\033[91m%s\033[39m\n" "$@" >&2; }
die () { say "$@"; exit 1; }


case $TESTENV in
    py34-cov)
        exe=/usr/bin/python3.4
        ;;
    py3*-pyqt*)
        exe=$(readlink -f .tox/$TESTENV/bin/python)
        ;;
    *)
        echo "Skipping coredump analysis in testenv $TESTENV!"
        exit 0
        ;;
esac

find . -name *.core -o -name core -exec gdb --batch --quiet -ex "thread apply all bt full" "$exe" {} \;
