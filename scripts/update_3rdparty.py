#!/usr/bin/python

"""Update 3rd-party files (currently only ez_setup.py)."""

from urllib.request import urlretrieve

urlretrieve('https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py',
            'scripts/ez_setup.py')
