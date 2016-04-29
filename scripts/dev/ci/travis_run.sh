#!/bin/bash

if [[ $DOCKER ]]; then
    # To build a fresh image:
    # docker build -t img misc/docker/$DOCKER
    # docker run --privileged -v $PWD:/outside img

    docker run --privileged -v $PWD:/outside \
        thecompiler/qutebrowser-manual:$DOCKER
else
    args=()
    [[ $TESTENV == docs ]] && args=('--no-authors')

    tox -e $TESTENV -- "${args[@]}"
fi
