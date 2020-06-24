#!/bin/bash

if [[ -n $DOCKER ]]; then
    docker run \
           --privileged \
           -v "$PWD:/outside" \
           -e "QUTE_BDD_WEBENGINE=$QUTE_BDD_WEBENGINE" \
           -e "DOCKER=$DOCKER" \
           -e "CI=$CI" \
           "qutebrowser/ci:$DOCKER"
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
           koalaman/shellcheck:stable "${scripts[@]}"
else
    args=()
    # We only run unit tests on macOS because it's quite slow.
    [[ $TRAVIS_OS_NAME == osx ]] && args+=('--qute-bdd-webengine' '--no-xvfb' 'tests/unit')

    # WORKAROUND for unknown crash inside swrast_dri.so
    # See https://github.com/qutebrowser/qutebrowser/pull/4218#issuecomment-421931770
    [[ $TESTENV == py36-pyqt59 ]] && export QT_QUICK_BACKEND=software

    tox -e "$TESTENV" -- "${args[@]}"
fi
