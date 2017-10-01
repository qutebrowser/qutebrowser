#!/bin/bash
#
#  Find all possible core files under current directory. Attempt
#  to determine exe using file(1) and dump stack trace with gdb.
#

case $TESTENV in
    py3*-pyqt*)
        exe=$(readlink -f .tox/$TESTENV/bin/python)
        full=
        ;;
    *)
        echo "Skipping coredump analysis in testenv $TESTENV!"
        exit 0
        ;;
esac

find . -name *.core -o -name core -exec gdb --batch --quiet -ex "thread apply all bt $full" "$exe" {} \;
