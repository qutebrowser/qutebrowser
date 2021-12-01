# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""A single tab."""

# pylint: disable=unused-import
from qutebrowser.browser.browsertab import WebTabError, AbstractTab as Tab
from qutebrowser.browser.inspector import (Position as InspectorPosition,
                                           Error as InspectorError)
from qutebrowser.browser.webelem import (Error as WebElemError,
                                         AbstractWebElement as WebElement)
from qutebrowser.utils.usertypes import ClickTarget, JsWorld
from qutebrowser.extensions.loader import InitContext
