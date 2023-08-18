# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A keyboard-driven, vim-like browser based on Python and Qt."""

import os.path

__author__ = "Florian Bruhin"
__copyright__ = "Copyright 2014-2021 Florian Bruhin (The Compiler)"
__license__ = "GPL"
__maintainer__ = __author__
__email__ = "mail@qutebrowser.org"
__version__ = "3.0.0"
__version_info__ = tuple(int(part) for part in __version__.split('.'))
__description__ = "A keyboard-driven, vim-like browser based on Python and Qt."

basedir = os.path.dirname(os.path.realpath(__file__))
