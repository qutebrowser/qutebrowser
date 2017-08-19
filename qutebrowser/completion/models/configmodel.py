# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions that return config-related completion models."""

from qutebrowser.config import configdata, configexc, config
from qutebrowser.completion.models import completionmodel, listcategory, util
from qutebrowser.commands import cmdutils


def option():
    """A CompletionModel filled with settings and their descriptions."""
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))
    options = ((x.name, x.description, config.instance.get_str(x.name))
               for x in configdata.DATA.values())
    model.add_category(listcategory.ListCategory("Options", options))
    return model


def value(optname, *_values):
    """A CompletionModel filled with setting values.

    Args:
        optname: The name of the config option this model shows.
        _values: The values already provided on the command line.
    """
    model = completionmodel.CompletionModel(column_widths=(30, 70, 0))

    try:
        current = str(config.instance.get(optname) or '""')
    except configexc.NoOptionError:
        return None

    opt = configdata.DATA[optname]
    default = str(opt.default or '""')
    cur_cat = listcategory.ListCategory("Current/Default",
        [(current, "Current value"), (default, "Default value")])
    model.add_category(cur_cat)

    vals = opt.typ.complete()
    if vals is not None:
        model.add_category(listcategory.ListCategory("Completions", vals))
    return model


def bind(key):
    """A CompletionModel filled with all bindable commands and descriptions.

    Args:
        key: the key being bound.
    """
    model = completionmodel.CompletionModel(column_widths=(20, 60, 20))
    cmd_text = config.key_instance.get_bindings_for('normal').get(key)

    if cmd_text:
        cmd_name = cmd_text.split(' ')[0]
        cmd = cmdutils.cmd_dict.get(cmd_name)
        data = [(cmd_text, cmd.desc, key)]
        model.add_category(listcategory.ListCategory("Current", data))

    cmdlist = util.get_cmd_completions(include_hidden=True,
                                       include_aliases=True)
    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    return model
