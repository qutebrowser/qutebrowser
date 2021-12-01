This directory contains a Dockerfile template for containers used to test
qutebrowser on CI.

The `generate.py` script uses that template to generate various image
configuration.

The images are rebuilt via Github Actions in this directory, and qutebrowser
then downloads them during the CI run. Note that means that it'll take a while
until builds will use the newer image if you make a change to this directory.
