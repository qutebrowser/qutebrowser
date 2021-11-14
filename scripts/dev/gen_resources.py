#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The-Compiler) <me@the-compiler.org>

# this file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation, either version 3 of the license, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Generate Qt resources based on source files."""

import subprocess
import pathlib

ROOT = pathlib.Path(__file__).parents[2]
OUTPUT = ROOT / 'qutebrowser' / 'resources.py'
INPUT = ROOT / 'misc' / 'qutebrowser.rcc'

subprocess.run(['pyrcc5', '-o', str(OUTPUT), str(INPUT)], check=True)
