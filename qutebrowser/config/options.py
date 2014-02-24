# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Setting options used for qutebrowser."""

from qutebrowser.config.templates import *

class ShowCompletion(BoolSettingValue):

    """Whether to show the autocompletion window or not."""

    default = "true"

class CompletionHeight(SettingValue):

    """The height of the completion, in px or as percentage of the window."""

    default = "50%"

    def validate(self, value):
        if value.endswith('%'):
            try:
                intval = int(value.rstrip('%'))
            except ValueError:
                return False
            else:
                return 0 <= intval <= 100
        else:
            try:
                intval = int(value)
            except ValueError:
                return False
            else:
                return intval > 0


class IgnoreCase(BoolSettingValue):

    """Whether to do case-insensitive searching."""

    default = "true"


class WrapSearch(BoolSettingValue):

    """Whether to wrap search to the top when arriving at the end."""

    default = "true"


class StartPage(ListSettingValue):

    """The default page(s) to open at the start, separated with commas."""

    default = "http://www.duckduckgo.com/"


class AutoSearch(BoolSettingValue):

    """Whether to start a search when something else than an URL is entered."""

    values = [("naive", "Use simple/naive check."),
              ("dns", "Use DNS requests (might be slow!)."),
              ("false": "Never search automatically.")]
    default = "naive"

    def validate(self, value):
        if value.lower() in ["naive", "dns"]:
            return True
        else:
            return super().validate(value)
            return True
        else:
            return super().validate(value)

    def transform(self, value):
        if value.lower() in ["naive", "dns"]:
            return value.lower()
        elif super().transform(value):
            # boolean true is an alias for naive matching
            return "naive"
        else:
            return "false"


class ZoomLevels(IntListSettingValue):

    """The available zoom levels, separated by commas."""

    default = "25,33,50,67,75,90,100,110,125,150,175,200,250,300,400,500"


class DefaultZoom(IntSettingValue):

    """The default zoom level."""

    # FIXME we might want to validate if defaultzoom is in zoomlevels...

    default = "100"


class Movable(BoolSettingValue):

    """Whether tabs should be movable."""

    default = "true"


class CloseButtons(BoolSettingValue):

    """Whether tabs should have close-buttons."""

    default = "false"


class ScrollButtons(BoolSettingValue):

    """Whether there should be scroll buttons if there are too many tabs."""

    default = "true"


class Position(SettingValue):

    """The position of the tab bar."""

    values = ["north", "south", "east", "west"]
    default = "north"


class SelectOnRemove(SettingValue):

    """Which tab to select when the focused tab is removed."""

    values = [("left", "Select the tab on the left."),
              ("right", "Select the tab on the right."),
              ("previous", "Select the previously selected tab.")]
    default = "previous"


class LastClose(SettingValue):

    """Behaviour when the last tab is closed."""

    values = [("ignore", "Don't do anything."),
              ("blank", "Load about:blank."),
              ("quit", "Quit qutebrowser.")]
    default = "ignore"

### FIXME what to do with list-style sections?

class SearchEngine(SettingValue):

    """A search engine setting."""

    def validate(self, value):
        return "{}" in value


class CompletionFgColor(ColorSettingValue):

    """Text color of the completion widget."""

    default = "#333333"


class CompletionItemBgColor(ColorSettingValue):

    """Background color of completion widget items."""

    default = "white"


class CompletionCategoryBgColor(ColorSettingValue):

    """Background color of the completion widget category headers."""

    default = ("completion.category.bg = qlineargradient("
               "x1:0, y1:0, x2:0, y2:1, stop:0 #e4e4e4, stop:1 #dbdbdb")


class CompletionCategoryTopBorderColor(ColorSettingValue):

    """Top border color of the completion widget category headers."""

    default = "#808080"


class CompletionCategoryBottomBorderColor(ColorSettingValue):

    """Bottom border color of the completion widget category headers."""

    default = "#bbbbbb"


class CompletionItemSelectedFgColor(ColorSettingValue):

    """Foreground color of the selected completion item."""

    default = "#333333"


class CompletionItemSelectedBgColor(ColorSettingValue):

    """Background color of the selected completion item."""

    default = "#ffec8b"


class CompletionItemSelectedTopBorderColor(ColorSettingValue):

    """Top border color of the selected completion item."""

    default = "#f2f2c0"


class CompletionItemSelectedBottomBorderColor(ColorSettingValue):

    """Bottom border color of the selected completion item."""

    default = "#ffec8b"


class CompletionMatchFgColor(ColorSettingValue):

    """Foreground color of the matched text in the completion."""

    default = "red"


class StatusbarBgColor(ColorSettingValue):

    """Background color of the statusbar."""

    default = "black"


class StatusbarFgColor(ColorSettingValue):

    """Foreground color of the statusbar."""

    default = "white"


class StatusbarFgErrorColor(ColorSettingValue):

    """Foreground color of the statusbar if there was an error."""

    default = "${statusbar.fg}"


class StatusbarBgErrorColor(ColorSettingValue):

    """Background color of the statusbar if there was an error."""

    default = "red"


class StatusbarProgressBgColor(ColorSettingValue):

    """Background color of the progress bar."""

    default = "white"


class StatusbarUrlFgColor(ColorSettingValue):

    """Default foreground color of the URL in the statusbar."""

    default = "${statusbar.fg}"


class StatusbarUrlSuccessFgColor(ColorSettingValue):

    """Foreground color of the URL in the statusbar on successful load."""

    default = "lime"


class StatusbarUrlErrorFgColor(ColorSettingValue):

    """Foreground color of the URL in the statusbar on error."""

    default = "orange"


class StatusbarUrlWarnFgColor(ColorSettingValue):

    """Foreground color of the URL in the statusbar when there's a warning."""

    default = "yellow"


class StatusbarUrlHoverFgColor(ColorSettingValue):

    """Foreground color of the URL in the statusbar for hovered links."""

    default = "aqua"


class TabFgColor(ColorSettingValue):

    """Foreground color of the tabbar."""

    default = "white"


class TabBgColor(ColorSettingValue):

    """Background color of the tabbar."""

    default = "grey"


class TabSelectedBgColor(ColorSettingValue):

    """Background color of the tabbar for the selected tab."""

    default = "black"


class TabSeperatorColor(ColorSettingValue):

    """Color for the tab seperator."""

    default = "white"


class MonospaceFonts(FontSettingValue):

    """Default monospace fonts."""

    default = ('Monospace, "DejaVu Sans Mono", Consolas, Monaco, '
               '"Bitstream Vera Sans Mono", "Andale Mono", "Liberation Mono", '
               '"Courier New", Courier, monospace, Fixed, Terminal')


class CompletionFont(FontSettingValue):

    """Font used in the completion widget."""

    default = "8pt ${_monospace}"


class TabbarFont(FontSettingValue):

    """Font used in the tabbar."""

    default = "8pt ${_monospace}"


class StatusbarFont(FontSettingValue):

    """Font used in the statusbar."""

    default = "8pt ${_monospace}"
