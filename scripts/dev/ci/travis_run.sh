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
elif [[ $TESTENV == shellcheck ]]; then
    SCRIPTS=$( mktemp )
    find scripts/dev/ -name '*.sh' >"$SCRIPTS"
    find misc/userscripts/ -type f -exec grep -lE '[/ ][bd]ash$|[/ ]sh$|[/ ]ksh$' {} + >>"$SCRIPTS"
    mapfile -t scripts <"$SCRIPTS"
    rm -f "$SCRIPTS"
    docker run \
           -v "$PWD:/outside" \
           -w /outside \
           koalaman/shellcheck:latest "${scripts[@]}"
else
    args=()
    [[ $TRAVIS_OS_NAME == osx ]] && args=('--qute-bdd-webengine' '--no-xvfb' 'tests/unit')

    tox -e "$TESTENV" -- "${args[@]}"
fi
