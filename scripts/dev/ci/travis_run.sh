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
    dev_scripts=$( find scripts/dev/ -name '*.sh' -print0 | xargs -0 )
    # false positive: we are using 'find -exec +'
    # shellcheck disable=SC2038
    userscripts=$( find misc/userscripts/ -type f -exec grep -lE '[/ ][bd]ash$|[/ ]sh$|[/ ]ksh$' {} + | xargs )
    IFS=" " read -r -a scripts <<< "$dev_scripts $userscripts"
    docker run \
           -v "$PWD:/outside" \
           -w /outside \
           koalaman/shellcheck:latest "${scripts[@]}"
else
    args=()
    [[ $TRAVIS_OS_NAME == osx ]] && args=('--qute-bdd-webengine' '--no-xvfb')

    tox -e "$TESTENV" -- "${args[@]}"
fi
