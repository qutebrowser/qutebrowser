#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A userscript to check if the stdin gets closed."""

import sys
import os
sys.stdin.read()
with open(os.environ['QUTE_FIFO'], 'wb') as fifo:
    fifo.write(b':message-info "stdin closed"\n')
