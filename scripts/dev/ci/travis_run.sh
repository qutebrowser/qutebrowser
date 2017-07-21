#!/bin/bash

if [[ $DOCKER ]]; then
    docker run --privileged -v $PWD:/outside -e QUTE_BDD_WEBENGINE=$QUTE_BDD_WEBENGINE -e DOCKER=$DOCKER qutebrowser/travis:$DOCKER
else
    args=()
    [[ $TRAVIS_OS_NAME == osx ]] && args=('--qute-bdd-webengine' '--no-xvfb')

    tox -e $TESTENV -- "${args[@]}"
fi
