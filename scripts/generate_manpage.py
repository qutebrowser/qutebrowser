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

"""Generate asciidoc source for qutebrowser based on docstrings."""

import os
import sys
import inspect

sys.path.insert(0, os.getcwd())

import qutebrowser.app
import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.configdata as configdata
from qutebrowser.utils.usertypes import enum


def parse_docstring(func):
    """Generates documentation based on a docstring of a command handler.

    The docstring needs to follow the format described in HACKING.

    Args:
        func: The function to generate the docstring for.

    Return:
        A (short_desc, long_desc, arg_descs) tuple.
    """
    State = enum('short', 'desc', 'arg_start', 'arg_inside')
    doc = inspect.getdoc(func)
    lines = doc.splitlines()

    cur_state = State.short

    short_desc = []
    long_desc = []
    arg_descs = {}
    cur_arg_name = None

    for line in lines:
        if cur_state == State.short:
            if not line:
                cur_state = State.desc
            else:
                short_desc.append(line.strip())
        elif cur_state == State.desc:
            if line.startswith('Args:'):
                cur_state = State.arg_start
            elif line.strip():
                long_desc.append(line.strip())
        elif cur_state == State.arg_start:
            cur_arg_name, argdesc = line.split(':', maxsplit=1)
            cur_arg_name = cur_arg_name.strip()
            arg_descs[cur_arg_name] = [argdesc.strip()]
            cur_state = State.arg_inside
        elif cur_state == State.arg_inside:
            if not line:
                break
            elif line[4:].startswith(' '):
                arg_descs[cur_arg_name].append(line.strip())
            else:
                cur_arg_name, argdesc = line.split(':', maxsplit=1)
                cur_arg_name = cur_arg_name.strip()
                arg_descs[cur_arg_name] = [argdesc.strip()]

    return (short_desc, long_desc, arg_descs)


def get_cmd_syntax(name, cmd):
    words = []
    argspec = inspect.getfullargspec(cmd.handler)
    if argspec.defaults is not None:
        defaults = dict(zip(reversed(argspec.args), reversed(list(argspec.defaults))))
    else:
        defaults = {}
    words.append(name)
    minargs, maxargs = cmd.nargs
    i = 1
    for arg in argspec.args:
        if arg in ['self', 'count']:
            continue
        if minargs is not None and i <= minargs:
            words.append('_<{}>_'.format(arg))
        elif maxargs is None or i <= maxargs:
            words.append('_[<{}>]_'.format(arg))
        i += 1
    return (' '.join(words), defaults)


def get_command_quickref(cmds):
    out = []
    out.append('[options="header",width="75%"]')
    out.append('|==============')
    out.append('|Command|Description')
    for name, cmd in cmds:
        desc = inspect.getdoc(cmd.handler).splitlines()[0]
        out.append('|{}|{}'.format(name, desc))
    out.append('|==============')
    return '\n'.join(out)


def get_setting_quickref():
    out = []
    for sectname, sect in configdata.DATA.items():
        if not getattr(sect, 'descriptions'):
            continue
        out.append(".Quick reference for section ``{}''".format(sectname))
        out.append('[options="header",width="75%"]')
        out.append('|==============')
        out.append('|Setting|Description')
        for optname, option in sect.items():
            desc = sect.descriptions[optname]
            out.append('|{}|{}'.format(optname, desc))
        out.append('|==============')
    return '\n'.join(out)


def get_command_doc(name, cmd):
    output = ['==== {}'.format(name)]
    syntax, defaults = get_cmd_syntax(name, cmd)
    output.append('+:{}+'.format(syntax))
    output.append("")
    short_desc, long_desc, arg_descs = parse_docstring(cmd.handler)
    output.append(' '.join(short_desc))
    output.append("")
    output.append(' '.join(long_desc))
    if arg_descs:
        output.append("")
        for arg, desc in arg_descs.items():
            item = "* +_{}_+: {}".format(arg, ' '.join(desc))
            if arg in defaults:
                item += " (default: +{}+)".format(defaults[arg])
            output.append(item)
        output.append("")
    output.append("")
    return '\n'.join(output)


def generate_commands():
    print()
    print("== Commands")
    normal_cmds = []
    hidden_cmds = []
    for name, cmd in cmdutils.cmd_dict.items():
        if cmd.hide:
            hidden_cmds.append((name, cmd))
        else:
            normal_cmds.append((name, cmd))
    normal_cmds.sort()
    hidden_cmds.sort()
    print()
    print("=== Normal commands")
    print(".Quick reference")
    print(get_command_quickref(normal_cmds))
    for name, cmd in normal_cmds:
        print(get_command_doc(name, cmd))
    print()
    print("=== Hidden commands")
    print(".Quick reference")
    print(get_command_quickref(hidden_cmds))
    for name, cmd in hidden_cmds:
        print(get_command_doc(name, cmd))


def generate_settings():
    print()
    print("== Settings")
    print(get_setting_quickref())
    for sectname, sect in configdata.DATA.items():
        print()
        print("=== {}".format(sectname))
        print(configdata.SECTION_DESC[sectname])
        if not getattr(sect, 'descriptions'):
            pass
        else:
            for optname, option in sect.items():
                print()
                print("==== {}".format(optname))
                print(sect.descriptions[optname])
                print()
                valid_values = option.typ.valid_values
                if valid_values is not None:
                    print("Valid values:")
                    print()
                    for val in valid_values:
                        try:
                            desc = valid_values.descriptions[val]
                            print(" * +{}+: {}".format(val, desc))
                        except KeyError:
                            print(" * +{}+".format(val))
                    print()
                if option.default:
                    print("Default: +pass:[{}]+".format(option.default))
                else:
                    print("Default: empty")



generate_settings()
generate_commands()
