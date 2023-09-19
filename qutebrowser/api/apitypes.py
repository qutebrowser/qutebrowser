# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A single tab."""

# pylint: disable=unused-import
from qutebrowser.browser.browsertab import WebTabError, AbstractTab as Tab
from qutebrowser.browser.inspector import (Position as InspectorPosition,
                                           Error as InspectorError)
from qutebrowser.browser.webelem import (Error as WebElemError,
                                         AbstractWebElement as WebElement)
from qutebrowser.utils.usertypes import ClickTarget, JsWorld
from qutebrowser.extensions.loader import InitContext
