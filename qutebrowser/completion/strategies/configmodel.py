# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions that return config-related completion models."""

from typing import Optional, Callable, Any

from qutebrowser.completion.strategies.strategy import CompletionStrategy
from qutebrowser.config import configdata, configexc
from qutebrowser.completion.models import completionmodel, listcategory, util
from qutebrowser.commands import runners, cmdexc
from qutebrowser.keyinput import keyutils
from qutebrowser.completion.completer import CompletionInfo


def option(*, info):
    """A CompletionModel filled with settings and their descriptions."""
    return _option(info, "Options", lambda opt: not opt.no_autoconfig)


def customized_option(*, info):
    """A CompletionModel filled with set settings and their descriptions."""
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))
    options = ((values.opt.name, values.opt.description,
                info.config.get_str(values.opt.name))
               for values in info.config
               if values)
    model.add_category(listcategory.ListCategory("Customized options",
                                                 options))
    return model


def list_option(*, info):
    """A CompletionModel filled with settings whose values are lists."""
    predicate = lambda opt: (isinstance(info.config.get_obj(opt.name),
                                        list) and not opt.no_autoconfig)
    return _option(info, "List options", predicate)


def dict_option(*, info):
    """A CompletionModel filled with settings whose values are dicts."""
    predicate = lambda opt: (isinstance(info.config.get_obj(opt.name),
                                        dict) and not opt.no_autoconfig)
    return _option(info, "Dict options", predicate)


class OptionMaker(CompletionStrategy):
    """A CompletionModel that is generated for several option sets.

    Args:
        info: The config info that can be passed through.
        title: The title of the options.
        predicate: The function for filtering out the options. Takes a single
                   argument.
    """
    COLUMN_WIDTHS = (20, 70, 10)

    def __init__(self, title: str, predicate: Callable[[Optional[Any]], bool]):
        super().__init__()
        self.title = title
        self.predicate = predicate

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> None:
        super().populate(*args, info=info)
        options = ((opt.name, opt.description, info.config.get_str(opt.name))
                   for opt in configdata.DATA.values()
                   if self.predicate(opt))
        self.model.add_category(listcategory.ListCategory(self.title, options))


class Value(CompletionStrategy):
    """A CompletionModel filled with setting values.

    Args:
        optname: The name of the config option this model shows.
        values: The values already provided on the command line.
        info: A CompletionInfo instance.
    """
    COLUMN_WIDTHS = (30, 70, 0)

    def __init__(self, optname, *values):
        super().__init__()
        self.optname = optname
        self.values = values

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> None:
        super().populate(*args, info=info)
        try:
            current = info.config.get_str(self.optname)
        except configexc.NoOptionError:
            return None

        opt = info.config.get_opt(self.optname)
        default = opt.typ.to_str(opt.default)
        cur_def = []
        if current not in self.values:
            cur_def.append((current, "Current value"))
        if default not in self.values:
            cur_def.append((default, "Default value"))
        if cur_def:
            cur_cat = listcategory.ListCategory("Current/Default", cur_def)
            self.model.add_category(cur_cat)

        vals = opt.typ.complete() or []
        vals = [x for x in vals if x[0] not in self.values]
        if vals:
            self.model.add_category(listcategory.ListCategory("Completions", vals))


class Bind(CompletionStrategy):
    """A CompletionModel filled with all bindable commands and descriptions.

    Args:
        key: the key being bound.
    """
    COLUMN_WIDTHS = (20, 60, 20)

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def _bind_current_default(self, info):
        """Get current/default data for the given key."""
        data = []
        try:
            seq = keyutils.KeySequence.parse(self.key)
        except keyutils.KeyParseError as e:
            data.append(('', str(e), self.key))
            return data

        cmd_text = info.keyconf.get_command(seq, 'normal')
        if cmd_text:
            parser = runners.CommandParser()
            try:
                cmd = parser.parse(cmd_text).cmd
            except cmdexc.NoSuchCommandError:
                data.append((cmd_text, '(Current) Invalid command!', self.key))
            else:
                data.append((cmd_text, '(Current) {}'.format(cmd.desc), self.key))

        cmd_text = info.keyconf.get_command(seq, 'normal', default=True)
        if cmd_text:
            parser = runners.CommandParser()
            cmd = parser.parse(cmd_text).cmd
            data.append((cmd_text, '(Default) {}'.format(cmd.desc), self.key))

        return data

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> None:
        super().populate(*args, info=info)
        data = self._bind_current_default(info)

        if data:
            self.model.add_category(listcategory.ListCategory("Current/Default", data))

        cmdlist = util.get_cmd_completions(info, include_hidden=True,
                                           include_aliases=True)
        self.model.add_category(listcategory.ListCategory("Commands", cmdlist))
