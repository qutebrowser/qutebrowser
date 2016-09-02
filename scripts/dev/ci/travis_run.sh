#!/bin/bash

if [[ $DOCKER ]]; then
    docker run --privileged -v $PWD:/outside qutebrowser/travis:$DOCKER
else
    args=()
    [[ $TESTENV == docs ]] && args=('--no-authors')

    tox -e $TESTENV -- "${args[@]}"
fi
