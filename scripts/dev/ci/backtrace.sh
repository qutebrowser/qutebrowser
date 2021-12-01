#!/bin/bash
#
#  Find all possible core files under current directory. Attempt
#  to determine exe using file(1) and dump stack trace with gdb.
#

testenv=$1

case $testenv in
    py3*-pyqt*)
        exe=$(readlink -f ".tox/$testenv/bin/python")
        full=
        ;;
    *)
        echo "Skipping coredump analysis in testenv $testenv!"
        exit 0
        ;;
esac

find . \( -name "*.core" -o -name core \) -exec gdb --batch --quiet -ex "thread apply all bt $full" "$exe" {} \;
