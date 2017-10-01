#!/bin/bash

if [[ $PWD == */scripts ]]; then
    cd ..
fi

echo > crash.log
while :; do
    exit=0
    while (( $exit == 0)); do
        duration=$(($RANDOM%10000))
        python3 -m qutebrowser --debug ":later $duration quit" http://www.heise.de/
        exit=$?
    done
    echo "$(date) $exit $duration" >> crash.log
done
