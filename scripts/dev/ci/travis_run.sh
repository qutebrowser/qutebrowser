#!/bin/bash

if [[ $DOCKER ]]; then
    docker run --privileged -v $PWD:/outside thecompiler/qutebrowser:$DOCKER
else
    args=()
    [[ $TESTENV == docs ]] && args=('--no-authors')

    tox -e $TESTENV -- "${args[@]}"
fi
