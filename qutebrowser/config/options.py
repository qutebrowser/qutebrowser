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

import qutebrowser.config.templates as template


class ShowCompletion(template.BoolSettingValue):

    """Whether to show the autocompletion window or not."""

    default = "true"


class CompletionHeight(template.SettingValue):

    """The height of the completion, in px or as percentage of the window."""

    default = "50%"

    def validate(self):
        if self.value.endswith('%'):
            try:
                intval = int(self.value.rstrip('%'))
            except ValueError:
                return False
            else:
                return 0 <= intval <= 100
        else:
            try:
                intval = int(self.value)
            except ValueError:
                return False
            else:
                return intval > 0


class IgnoreCase(template.BoolSettingValue):

    """Whether to do case-insensitive searching."""

    default = "true"


class WrapSearch(template.BoolSettingValue):

    """Whether to wrap search to the top when arriving at the end."""

    default = "true"


class StartPage(template.ListSettingValue):

    """The default page(s) to open at the start, separated with commas."""

    default = "http://www.duckduckgo.com/"


class AutoSearch(template.BoolSettingValue):

    """Whether to start a search when something else than an URL is entered."""

    valid_values = [("naive", "Use simple/naive check."),
                    ("dns", "Use DNS requests (might be slow!)."),
                    ("false", "Never search automatically.")]
    default = "naive"

    def validate(self):
        if self.value.lower() in ["naive", "dns"]:
            return True
        else:
            return super().validate(self.value)

    def transform(self, value):
        if value.lower() in ["naive", "dns"]:
            return value.lower()
        elif super().transform(value):
            # boolean true is an alias for naive matching
            return "naive"
        else:
            return False


class ZoomLevels(template.IntListSettingValue):

    """The available zoom levels, separated by commas."""

    default = "25,33,50,67,75,90,100,110,125,150,175,200,250,300,400,500"


class DefaultZoom(template.IntSettingValue):

    """The default zoom level."""

    # FIXME we might want to validate if defaultzoom is in zoomlevels...

    default = "100"


class Movable(template.BoolSettingValue):

    """Whether tabs should be movable."""

    default = "true"


class CloseButtons(template.BoolSettingValue):

    """Whether tabs should have close-buttons."""

    default = "false"


class ScrollButtons(template.BoolSettingValue):

    """Whether there should be scroll buttons if there are too many tabs."""

    default = "true"


class Position(template.StringSettingValue):

    """The position of the tab bar."""

    valid_values = ["north", "south", "east", "west"]
    default = "north"


class SelectOnRemove(template.StringSettingValue):

    """Which tab to select when the focused tab is removed."""

    valid_values = [("left", "Select the tab on the left."),
                    ("right", "Select the tab on the right."),
                    ("previous", "Select the previously selected tab.")]
    default = "previous"


class LastClose(template.StringSettingValue):

    """Behaviour when the last tab is closed."""

    valid_values = [("ignore", "Don't do anything."),
                    ("blank", "Load about:blank."),
                    ("quit", "Quit qutebrowser.")]
    default = "ignore"


class CompletionFgColor(template.ColorSettingValue):

    """Text color of the completion widget."""

    default = "#333333"


class CompletionItemBgColor(template.ColorSettingValue):

    """Background color of completion widget items."""

    default = "white"


class CompletionCategoryBgColor(template.ColorSettingValue):

    """Background color of the completion widget category headers."""

    default = ("qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e4e4e4, "
               "stop:1 #dbdbdb)")


class CompletionCategoryTopBorderColor(template.ColorSettingValue):

    """Top border color of the completion widget category headers."""

    default = "#808080"


class CompletionCategoryBottomBorderColor(template.ColorSettingValue):

    """Bottom border color of the completion widget category headers."""

    default = "#bbbbbb"


class CompletionItemSelectedFgColor(template.ColorSettingValue):

    """Foreground color of the selected completion item."""

    default = "#333333"


class CompletionItemSelectedBgColor(template.ColorSettingValue):

    """Background color of the selected completion item."""

    default = "#ffec8b"


class CompletionItemSelectedTopBorderColor(template.ColorSettingValue):

    """Top border color of the selected completion item."""

    default = "#f2f2c0"


class CompletionItemSelectedBottomBorderColor(template.ColorSettingValue):

    """Bottom border color of the selected completion item."""

    default = "#ffec8b"


class CompletionMatchFgColor(template.ColorSettingValue):

    """Foreground color of the matched text in the completion."""

    default = "red"


class StatusbarBgColor(template.ColorSettingValue):

    """Background color of the statusbar."""

    default = "black"


class StatusbarFgColor(template.ColorSettingValue):

    """Foreground color of the statusbar."""

    default = "white"


class StatusbarFgErrorColor(template.ColorSettingValue):

    """Foreground color of the statusbar if there was an error."""

    default = StatusbarFgColor.default
    default_conf = "${statusbar.fg}"


class StatusbarBgErrorColor(template.ColorSettingValue):

    """Background color of the statusbar if there was an error."""

    default = "red"


class StatusbarProgressBgColor(template.ColorSettingValue):

    """Background color of the progress bar."""

    default = "white"


class StatusbarUrlFgColor(template.ColorSettingValue):

    """Default foreground color of the URL in the statusbar."""

    default = StatusbarFgColor.default
    default_conf = "${statusbar.fg}"


class StatusbarUrlSuccessFgColor(template.ColorSettingValue):

    """Foreground color of the URL in the statusbar on successful load."""

    default = "lime"


class StatusbarUrlErrorFgColor(template.ColorSettingValue):

    """Foreground color of the URL in the statusbar on error."""

    default = "orange"


class StatusbarUrlWarnFgColor(template.ColorSettingValue):

    """Foreground color of the URL in the statusbar when there's a warning."""

    default = "yellow"


class StatusbarUrlHoverFgColor(template.ColorSettingValue):

    """Foreground color of the URL in the statusbar for hovered links."""

    default = "aqua"


class TabFgColor(template.ColorSettingValue):

    """Foreground color of the tabbar."""

    default = "white"


class TabBgColor(template.ColorSettingValue):

    """Background color of the tabbar."""

    default = "grey"


class TabSelectedBgColor(template.ColorSettingValue):

    """Background color of the tabbar for the selected tab."""

    default = "black"


class TabSeperatorColor(template.ColorSettingValue):

    """Color for the tab seperator."""

    default = "white"


class MonospaceFonts(template.FontSettingValue):

    """Default monospace fonts."""

    default = ('Monospace, "DejaVu Sans Mono", Consolas, Monaco, '
               '"Bitstream Vera Sans Mono", "Andale Mono", "Liberation Mono", '
               '"Courier New", Courier, monospace, Fixed, Terminal')


class CompletionFont(template.FontSettingValue):

    """Font used in the completion widget."""

    default = MonospaceFonts.default
    default_conf = "8pt ${_monospace}"


class TabbarFont(template.FontSettingValue):

    """Font used in the tabbar."""

    default = MonospaceFonts.default
    default_conf = "8pt ${_monospace}"


class StatusbarFont(template.FontSettingValue):

    """Font used in the statusbar."""

    default = MonospaceFonts.default
    default_conf = "8pt ${_monospace}"


class SearchEngineName(template.SettingValue):

    """A search engine name."""

    def validate(self):
        return True


class SearchEngineUrl(template.SettingValue):

    """A search engine URL."""

    def validate(self):
        return "{}" in self.value


class KeyBindingName(template.SettingValue):

    """The name (keys) of a keybinding."""

    def validate(self):
        # FIXME can we validate anything here?
        return True


class KeyBinding(template.CommandSettingValue):

    """The command of a keybinding."""

    pass
