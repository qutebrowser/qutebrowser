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

from qutebrowser.config import configdata, configexc
from qutebrowser.completion.models import completionmodel, listcategory
from qutebrowser.utils import objreg


def section():
    """A CompletionModel filled with settings sections."""
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))
    sections = ((name, configdata.SECTION_DESC[name].splitlines()[0].strip())
                for name in configdata.DATA)
    model.add_category(listcategory.ListCategory("Sections", sorted(sections)))
    return model


def option(sectname):
    """A CompletionModel filled with settings and their descriptions.

    Args:
        sectname: The name of the config section this model shows.
    """
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))
    try:
        sectdata = configdata.DATA[sectname]
    except KeyError:
        return None
    options = []
    for name in sectdata:
        try:
            desc = sectdata.descriptions[name]
        except (KeyError, AttributeError):
            # Some stuff (especially ValueList items) don't have a
            # description.
            desc = ""
        else:
            desc = desc.splitlines()[0]
        config = objreg.get('config')
        val = config.get(sectname, name, raw=True)
        options.append((name, desc, val))
    model.add_category(listcategory.ListCategory(sectname, sorted(options)))
    return model


def value(sectname, optname):
    """A CompletionModel filled with setting values.

    Args:
        sectname: The name of the config section this model shows.
        optname: The name of the config option this model shows.
    """
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))
    config = objreg.get('config')

    try:
        current = config.get(sectname, optname, raw=True) or '""'
    except (configexc.NoSectionError, configexc.NoOptionError):
        return None

    default = configdata.DATA[sectname][optname].default() or '""'

    if hasattr(configdata.DATA[sectname], 'valtype'):
        # Same type for all values (ValueList)
        vals = configdata.DATA[sectname].valtype.complete()
    else:
        if optname is None:
            raise ValueError("optname may only be None for ValueList "
                             "sections, but {} is not!".format(sectname))
        # Different type for each value (KeyValue)
        vals = configdata.DATA[sectname][optname].typ.complete()

    cur_cat = listcategory.ListCategory("Current/Default",
        [(current, "Current value"), (default, "Default value")])
    model.add_category(cur_cat)
    if vals is not None:
        model.add_category(listcategory.ListCategory("Completions",
                                                     sorted(vals)))
    return model
