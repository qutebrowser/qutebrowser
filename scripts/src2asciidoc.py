#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import html
import shutil
import os.path
import inspect
import subprocess
import collections
import tempfile
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

# We import qutebrowser.app so all @cmdutils-register decorators are run.
import qutebrowser.app
from scripts import asciidoc2html, utils
from qutebrowser import qutebrowser
from qutebrowser.commands import cmdutils
from qutebrowser.config import configdata
from qutebrowser.utils import docutils


class UsageFormatter(argparse.HelpFormatter):

    """Patched HelpFormatter to include some asciidoc markup in the usage.

    This does some horrible things, but the alternative would be to reimplement
    argparse.HelpFormatter while copying 99% of the code :-/
    """

    def _format_usage(self, usage, actions, groups, _prefix):
        """Override _format_usage to not add the 'usage:' prefix."""
        return super()._format_usage(usage, actions, groups, '')

    def _metavar_formatter(self, action, default_metavar):
        """Override _metavar_formatter to add asciidoc markup to metavars.

        Most code here is copied from Python 3.4's argparse.py.
        """
        if action.metavar is not None:
            result = "'{}'".format(action.metavar)
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            result = '{%s}' % ','.join('*{}*'.format(e) for e in choice_strs)
        else:
            result = "'{}'".format(default_metavar)

        def fmt(tuple_size):
            """Format the result according to the tuple size."""
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return fmt

    def _format_actions_usage(self, actions, groups):
        """Override _format_actions_usage to add asciidoc markup to flags.

        Because argparse.py's _format_actions_usage is very complex, we first
        monkey-patch the option strings to include the asciidoc markup, then
        run the original method, then undo the patching.
        """
        old_option_strings = {}
        for action in actions:
            old_option_strings[action] = action.option_strings[:]
            action.option_strings = ['*{}*'.format(s)
                                     for s in action.option_strings]
        ret = super()._format_actions_usage(actions, groups)
        for action in actions:
            action.option_strings = old_option_strings[action]
        return ret


def _open_file(name, mode='w'):
    """Open a file with a preset newline/encoding mode."""
    return open(name, mode, newline='\n', encoding='utf-8')


def _get_cmd_syntax(_name, cmd):
    """Get the command syntax for a command.

    We monkey-patch the parser's formatter_class here to use our UsageFormatter
    which adds some asciidoc markup.
    """
    old_fmt_class = cmd.parser.formatter_class
    cmd.parser.formatter_class = UsageFormatter
    usage = cmd.parser.format_usage().rstrip()
    cmd.parser.formatter_class = old_fmt_class
    return usage


def _get_command_quickref(cmds):
    """Generate the command quick reference."""
    out = []
    out.append('[options="header",width="75%",cols="25%,75%"]')
    out.append('|==============')
    out.append('|Command|Description')
    for name, cmd in cmds:
        desc = inspect.getdoc(cmd.handler).splitlines()[0]
        out.append('|<<{},{}>>|{}'.format(name, name, desc))
    out.append('|==============')
    return '\n'.join(out)


def _get_setting_quickref():
    """Generate the settings quick reference."""
    out = []
    for sectname, sect in configdata.DATA.items():
        if not getattr(sect, 'descriptions'):
            continue
        out.append("")
        out.append(".Quick reference for section ``{}''".format(sectname))
        out.append('[options="header",width="75%",cols="25%,75%"]')
        out.append('|==============')
        out.append('|Setting|Description')
        for optname, _option in sect.items():
            desc = sect.descriptions[optname].splitlines()[0]
            out.append('|<<{}-{},{}>>|{}'.format(
                sectname, optname, optname, desc))
        out.append('|==============')
    return '\n'.join(out)


def _get_command_doc(name, cmd):
    """Generate the documentation for a command."""
    output = ['[[{}]]'.format(name)]
    output += ['=== {}'.format(name)]
    syntax = _get_cmd_syntax(name, cmd)
    if syntax != name:
        output.append('Syntax: +:{}+'.format(syntax))
        output.append("")
    parser = docutils.DocstringParser(cmd.handler)
    output.append(parser.short_desc)
    if parser.long_desc:
        output.append("")
        output.append(parser.long_desc)

    if cmd.pos_args:
        output.append("")
        output.append("==== positional arguments")
        for arg, name in cmd.pos_args:
            try:
                output.append("* +'{}'+: {}".format(name,
                                                    parser.arg_descs[arg]))
            except KeyError as e:
                raise KeyError("No description for arg {} of command "
                               "'{}'!".format(e, cmd.name))

    if cmd.opt_args:
        output.append("")
        output.append("==== optional arguments")
        for arg, (long_flag, short_flag) in cmd.opt_args.items():
            try:
                output.append('* +*{}*+, +*{}*+: {}'.format(
                    short_flag, long_flag, parser.arg_descs[arg]))
            except KeyError:
                raise KeyError("No description for arg {} of command "
                               "'{}'!".format(e, cmd.name))

    if cmd.special_params['count'] is not None:
        output.append("")
        output.append("==== count")
        output.append(parser.arg_descs[cmd.special_params['count']])

    output.append("")
    output.append("")
    return '\n'.join(output)


def _get_action_metavar(action):
    """Get the metavar to display for an argparse action."""
    if action.metavar is not None:
        return "'{}'".format(action.metavar)
    elif action.choices is not None:
        choices = ','.join(map(str, action.choices))
        return "'{{{}}}'".format(choices)
    else:
        return "'{}'".format(action.dest.upper())


def _format_action_args(action):
    """Get an argument string based on an argparse action."""
    if action.nargs is None:
        return _get_action_metavar(action)
    elif action.nargs == '?':
        return '[{}]'.format(_get_action_metavar(action))
    elif action.nargs == '*':
        return '[{mv} [{mv} ...]]'.format(mv=_get_action_metavar(action))
    elif action.nargs == '+':
        return '{mv} [{mv} ...]'.format(mv=_get_action_metavar(action))
    elif action.nargs == '...':
        return '...'
    else:
        return ' '.join([_get_action_metavar(action)] * action.nargs)


def _format_action(action):
    """Get an invocation string/help from an argparse action."""
    if not action.option_strings:
        invocation = '*{}*::'.format(_get_action_metavar(action))
    else:
        parts = []
        if action.nargs == 0:
            # Doesn't take a value, so the syntax is -s, --long
            parts += ['*{}*'.format(s) for s in action.option_strings]
        else:
            # Takes a value, so the syntax is -s ARGS or --long ARGS.
            args_string = _format_action_args(action)
            for opt in action.option_strings:
                parts.append('*{}* {}'.format(opt, args_string))
        invocation = ', '.join(parts) + '::'
    return '{}\n    {}\n'.format(invocation, action.help)


def generate_commands(filename):
    """Generate the complete commands section."""
    with _open_file(filename) as f:
        f.write("= Commands\n")
        normal_cmds = []
        hidden_cmds = []
        debug_cmds = []
        for name, cmd in cmdutils.cmd_dict.items():
            if name in cmdutils.aliases:
                continue
            if cmd.hide:
                hidden_cmds.append((name, cmd))
            elif cmd.debug:
                debug_cmds.append((name, cmd))
            else:
                normal_cmds.append((name, cmd))
        normal_cmds.sort()
        hidden_cmds.sort()
        debug_cmds.sort()
        f.write("\n")
        f.write("== Normal commands\n")
        f.write(".Quick reference\n")
        f.write(_get_command_quickref(normal_cmds) + '\n')
        for name, cmd in normal_cmds:
            f.write(_get_command_doc(name, cmd))
        f.write("\n")
        f.write("== Hidden commands\n")
        f.write(".Quick reference\n")
        f.write(_get_command_quickref(hidden_cmds) + '\n')
        for name, cmd in hidden_cmds:
            f.write(_get_command_doc(name, cmd))
        f.write("\n")
        f.write("== Debugging commands\n")
        f.write("These commands are mainly intended for debugging. They are "
                "hidden if qutebrowser was started without the "
                "`--debug`-flag.\n")
        f.write("\n")
        f.write(".Quick reference\n")
        f.write(_get_command_quickref(debug_cmds) + '\n')
        for name, cmd in debug_cmds:
            f.write(_get_command_doc(name, cmd))


def generate_settings(filename):
    """Generate the complete settings section."""
    with _open_file(filename) as f:
        f.write("= Settings\n")
        f.write(_get_setting_quickref() + "\n")
        for sectname, sect in configdata.DATA.items():
            f.write("\n")
            f.write("== {}".format(sectname) + "\n")
            f.write(configdata.SECTION_DESC[sectname] + "\n")
            if not getattr(sect, 'descriptions'):
                pass
            else:
                for optname, option in sect.items():
                    f.write("\n")
                    f.write('[[{}-{}]]'.format(sectname, optname) + "\n")
                    f.write("=== {}".format(optname) + "\n")
                    f.write(sect.descriptions[optname] + "\n")
                    f.write("\n")
                    valid_values = option.typ.valid_values
                    if valid_values is not None:
                        f.write("Valid values:\n")
                        f.write("\n")
                        for val in valid_values:
                            try:
                                desc = valid_values.descriptions[val]
                                f.write(" * +{}+: {}".format(val, desc) + "\n")
                            except KeyError:
                                f.write(" * +{}+".format(val) + "\n")
                        f.write("\n")
                    if option.default():
                        f.write("Default: +pass:[{}]+\n".format(html.escape(
                            option.default())))
                    else:
                        f.write("Default: empty\n")


def _get_authors():
    """Get a list of authors based on git commit logs."""
    commits = subprocess.check_output(['git', 'log', '--format=%aN'])
    cnt = collections.Counter(commits.decode('utf-8').splitlines())
    return sorted(cnt, key=lambda k: (cnt[k], k), reverse=True)


def _format_block(filename, what, data):
    """Format a block in a file.

    The block is delimited by markers like these:
        // QUTE_*_START
        ...
        // QUTE_*_END

    The * part is the part which should be given as 'what'.

    Args:
        filename: The file to change.
        what: What to change (authors, options, etc.)
        data; A list of strings which is the new data.
    """
    what = what.upper()
    oshandle, tmpname = tempfile.mkstemp()
    try:
        with _open_file(filename, mode='r') as infile, \
                _open_file(oshandle, mode='w') as temp:
            found_start = False
            found_end = False
            for line in infile:
                if line.strip() == '// QUTE_{}_START'.format(what):
                    temp.write(line)
                    temp.write(''.join(data))
                    found_start = True
                elif line.strip() == '// QUTE_{}_END'.format(what.upper()):
                    temp.write(line)
                    found_end = True
                elif (not found_start) or found_end:
                    temp.write(line)
        if not found_start:
            raise Exception("Marker '// QUTE_{}_START' not found in "
                            "'{}'!".format(what, filename))
        elif not found_end:
            raise Exception("Marker '// QUTE_{}_END' not found in "
                            "'{}'!".format(what, filename))
    except:  # pylint: disable=bare-except
        os.remove(tmpname)
        raise
    else:
        os.remove(filename)
        shutil.move(tmpname, filename)


def regenerate_authors(filename):
    """Re-generate the authors inside README based on the commits made."""
    data = ['* {}\n'.format(author) for author in _get_authors()]
    _format_block(filename, 'authors', data)


def regenerate_manpage(filename):
    """Update manpage OPTIONS using an argparse parser."""
    # pylint: disable=protected-access
    parser = qutebrowser.get_argparser()
    groups = []
    # positionals, optionals and user-defined groups
    for group in parser._action_groups:
        groupdata = []
        groupdata.append('=== {}'.format(group.title))
        if group.description is not None:
            groupdata.append(group.description)
        for action in group._group_actions:
            groupdata.append(_format_action(action))
        groups.append('\n'.join(groupdata))
    options = '\n'.join(groups)
    # epilog
    if parser.epilog is not None:
        options.append(parser.epilog)
    _format_block(filename, 'options', options)


def main():
    """Regenerate all documentation."""
    utils.change_cwd()
    print("Generating manpage...")
    regenerate_manpage('doc/qutebrowser.1.asciidoc')
    print("Generating settings help...")
    generate_settings('doc/help/settings.asciidoc')
    print("Generating command help...")
    generate_commands('doc/help/commands.asciidoc')
    print("Generating authors in README...")
    regenerate_authors('README.asciidoc')
    if '--html' in sys.argv:
        asciidoc2html.main()


if __name__ == '__main__':
    main()
