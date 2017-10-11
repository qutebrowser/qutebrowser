#!/bin/bash

if [[ $DOCKER ]]; then
    docker run \
           --privileged \
           -v "$PWD:/outside" \
           -e "QUTE_BDD_WEBENGINE=$QUTE_BDD_WEBENGINE" \
           -e "DOCKER=$DOCKER" \
           -e "CI=$CI" \
           -e "TRAVIS=$TRAVIS" \
           "qutebrowser/travis:$DOCKER"
elif [[ $TESTENV == eslint ]]; then
    # Can't run this via tox as we can't easily install tox in the javascript
    # travis env
    cd qutebrowser/javascript || exit 1
    eslint --color --report-unused-disable-directives .
else
    args=()
    [[ $TRAVIS_OS_NAME == osx ]] && args=('--qute-bdd-webengine' '--no-xvfb')

    tox -e "$TESTENV" -- "${args[@]}"
fi
