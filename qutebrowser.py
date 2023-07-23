#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simple launcher for qutebrowser."""

import sys

import qutebrowser.qutebrowser


if __name__ == '__main__':
    sys.exit(qutebrowser.qutebrowser.main())
