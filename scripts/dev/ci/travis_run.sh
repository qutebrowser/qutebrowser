#!/bin/bash

if [[ $DOCKER ]]; then
    docker build -t img misc/docker/$DOCKER
    docker run --privileged -v $PWD:/outside img
else
    args=()
    [[ $TESTENV == docs ]] && args=('--no-authors')

    tox -e $TESTENV -- "${args[@]}"
fi
