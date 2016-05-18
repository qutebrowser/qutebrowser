#!/bin/bash

# Strip trailing whitespace from files in this repo

find qutebrowser scripts tests \
    -type f \( \
        -name '*.py' -o \
        -name '*.feature' -o \
        -name '*.sh' \
    \) -exec sed -i 's/ \+$//' {} +
