#!/bin/bash

if [[ $DOCKER ]]; then
    docker run --privileged -v $PWD:/outside -e QUTE_BDD_WEBENGINE=$QUTE_BDD_WEBENGINE qutebrowser/travis:$DOCKER
else
    args=()
    [[ $TESTENV == docs ]] && args=('--no-authors')

    tox -e $TESTENV -- "${args[@]}"
fi
