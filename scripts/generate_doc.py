#!/usr/bin/python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import re
import os
import sys
import html
import shutil
import inspect
import subprocess
import collections
import tempfile

sys.path.insert(0, os.getcwd())

import qutebrowser
# We import qutebrowser.app so all @cmdutils-register decorators are run.
import qutebrowser.app
from qutebrowser import qutebrowser as qutequtebrowser
from qutebrowser.commands import cmdutils
from qutebrowser.config import configdata
from qutebrowser.utils import usertypes


def _open_file(name, mode='w'):
    """Open a file with a preset newline/encoding mode."""
    return open(name, mode, newline='\n', encoding='utf-8')


def _parse_docstring(func):  # noqa
    """Generate documentation based on a docstring of a command handler.

    The docstring needs to follow the format described in HACKING.

    Args:
        func: The function to generate the docstring for.

    Return:
        A (short_desc, long_desc, arg_descs) tuple.
    """
    # pylint: disable=too-many-branches
    State = usertypes.enum('State', 'short',  # pylint: disable=invalid-name
                           'desc', 'desc_hidden', 'arg_start', 'arg_inside',
                           'misc')
    doc = inspect.getdoc(func)
    lines = doc.splitlines()

    cur_state = State.short

    short_desc = []
    long_desc = []
    arg_descs = collections.OrderedDict()
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
            elif line.startswith('Emit:') or line.startswith('Raise:'):
                cur_state = State.misc
            elif line.strip() == '//':
                cur_state = State.desc_hidden
            elif line.strip():
                long_desc.append(line.strip())
        elif cur_state == State.misc:
            if line.startswith('Args:'):
                cur_state = State.arg_start
            else:
                pass
        elif cur_state == State.desc_hidden:
            if line.startswith('Args:'):
                cur_state = State.arg_start
        elif cur_state == State.arg_start:
            cur_arg_name, argdesc = line.split(':', maxsplit=1)
            cur_arg_name = cur_arg_name.strip().lstrip('*')
            arg_descs[cur_arg_name] = [argdesc.strip()]
            cur_state = State.arg_inside
        elif cur_state == State.arg_inside:
            if re.match('^[A-Z][a-z]+:$', line):
                if not arg_descs[cur_arg_name][-1].strip():
                    arg_descs[cur_arg_name] = arg_descs[cur_arg_name][:-1]
                    break
            elif not line.strip():
                arg_descs[cur_arg_name].append('\n\n')
            elif line[4:].startswith(' '):
                arg_descs[cur_arg_name].append(line.strip() + '\n')
            else:
                cur_arg_name, argdesc = line.split(':', maxsplit=1)
                cur_arg_name = cur_arg_name.strip().lstrip('*')
                arg_descs[cur_arg_name] = [argdesc.strip()]
    return (short_desc, long_desc, arg_descs)


def _get_cmd_syntax(name, cmd):
    """Get the command syntax for a command."""
    words = []
    argspec = inspect.getfullargspec(cmd.handler)
    if argspec.defaults is not None:
        defaults = dict(zip(reversed(argspec.args),
                        reversed(list(argspec.defaults))))
    else:
        defaults = {}
    words.append(name)
    minargs, maxargs = cmd.nargs
    i = 1
    for arg in argspec.args:
        if arg in ['self', 'count']:
            continue
        if minargs is not None and i <= minargs:
            words.append('<{}>'.format(arg))
        elif maxargs is None or i <= maxargs:
            words.append('[<{}>]'.format(arg))
        i += 1
    if argspec.varargs is not None:
        words.append('[<{name}> [...]]'.format(name=argspec.varargs))
    return (' '.join(words), defaults)


def _get_command_quickref(cmds):
    """Generate the command quick reference."""
    out = []
    out.append('[options="header",width="75%",cols="25%,75%"]')
    out.append('|==============')
    out.append('|Command|Description')
    for name, cmd in cmds:
        desc = inspect.getdoc(cmd.handler).splitlines()[0]
        out.append('|<<cmd-{},{}>>|{}'.format(name, name, desc))
    out.append('|==============')
    return '\n'.join(out)


def _get_setting_quickref():
    """Generate the settings quick reference."""
    out = []
    for sectname, sect in configdata.DATA.items():
        if not getattr(sect, 'descriptions'):
            continue
        out.append(".Quick reference for section ``{}''".format(sectname))
        out.append('[options="header",width="75%",cols="25%,75%"]')
        out.append('|==============')
        out.append('|Setting|Description')
        for optname, _option in sect.items():
            desc = sect.descriptions[optname].splitlines()[0]
            out.append('|<<setting-{}-{},{}>>|{}'.format(
                sectname, optname, optname, desc))
        out.append('|==============')
    return '\n'.join(out)


def _get_command_doc(name, cmd):
    """Generate the documentation for a command."""
    output = ['[[cmd-{}]]'.format(name)]
    output += ['==== {}'.format(name)]
    syntax, defaults = _get_cmd_syntax(name, cmd)
    if syntax != name:
        output.append('Syntax: +:{}+'.format(syntax))
    output.append("")
    short_desc, long_desc, arg_descs = _parse_docstring(cmd.handler)
    output.append(' '.join(short_desc))
    output.append("")
    output.append(' '.join(long_desc))
    if arg_descs:
        output.append("")
        for arg, desc in arg_descs.items():
            text = ' '.join(desc).splitlines()
            firstline = text[0].replace(', or None', '')
            item = "* +{}+: {}".format(arg, firstline)
            if arg in defaults:
                val = defaults[arg]
                if val is None:
                    item += " (optional)\n"
                else:
                    item += " (default: +{}+)\n".format(defaults[arg])
            item += '\n'.join(text[1:])
            output.append(item)
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
    return '{}\n    {}\n\n'.format(invocation, action.help)


def generate_manpage_header(f):
    """Generate an asciidoc header for the manpage."""
    f.write("// DO NOT EDIT THIS FILE BY HAND!\n")
    f.write("// It is generated by `scripts/generate_doc.py`.\n")
    f.write("// Most likely you'll need to rerun that script, or edit that "
            "instead of this file.\n")
    f.write('= qutebrowser(1)\n')
    f.write(':doctype: manpage\n')
    f.write(':man source: qutebrowser\n')
    f.write(':man manual: qutebrowser manpage\n')
    f.write(':toc:\n')
    f.write(':homepage: http://www.qutebrowser.org/\n')
    f.write('\n')


def generate_manpage_name(f):
    """Generate the NAME-section of the manpage."""
    f.write('== NAME\n')
    f.write('qutebrowser - {}\n'.format(qutebrowser.__description__))
    f.write('\n')


def generate_manpage_synopsis(f):
    """Generate the SYNOPSIS-section of the manpage."""
    f.write('== SYNOPSIS\n')
    f.write("*qutebrowser* ['-OPTION' ['...']] [':COMMAND' ['...']] "
            "['URL' ['...']]\n")
    f.write('\n')


def generate_manpage_description(f):
    """Generate the DESCRIPTION-section of the manpage."""
    f.write('== DESCRIPTION\n')
    f.write("qutebrowser is a keyboard-focused browser with with a minimal "
            "GUI. It's based on Python, PyQt5 and QtWebKit and free software, "
            "licensed under the GPL.\n\n")
    f.write("It was inspired by other browsers/addons like dwb and "
            "Vimperator/Pentadactyl.\n\n")


def generate_manpage_options(f):
    """Generate the OPTIONS-section of the manpage from an argparse parser."""
    # pylint: disable=protected-access
    parser = qutequtebrowser.get_argparser()
    f.write('== OPTIONS\n')

    # positionals, optionals and user-defined groups
    for group in parser._action_groups:
        f.write('=== {}\n'.format(group.title))
        if group.description is not None:
            f.write(group.description + '\n')
        for action in group._group_actions:
            f.write(_format_action(action))
        f.write('\n')
    # epilog
    if parser.epilog is not None:
        f.write(parser.epilog)
    f.write('\n')


def generate_commands(f):
    """Generate the complete commands section."""
    f.write('\n')
    f.write("== COMMANDS\n")
    normal_cmds = []
    hidden_cmds = []
    debug_cmds = []
    for name, cmd in cmdutils.cmd_dict.items():
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
    f.write("=== Normal commands\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(normal_cmds) + "\n")
    for name, cmd in normal_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")
    f.write("\n")
    f.write("=== Hidden commands\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(hidden_cmds) + "\n")
    for name, cmd in hidden_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")
    f.write("\n")
    f.write("=== Debugging commands\n")
    f.write("These commands are mainly intended for debugging. They are "
            "hidden if qutebrowser was started without the `--debug`-flag.\n")
    f.write("\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(debug_cmds) + "\n")
    for name, cmd in debug_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")


def generate_settings(f):
    """Generate the complete settings section."""
    f.write("\n")
    f.write("== SETTINGS\n")
    f.write(_get_setting_quickref() + "\n")
    for sectname, sect in configdata.DATA.items():
        f.write("\n")
        f.write("=== {}".format(sectname) + "\n")
        f.write(configdata.SECTION_DESC[sectname] + "\n")
        if not getattr(sect, 'descriptions'):
            pass
        else:
            for optname, option in sect.items():
                f.write("\n")
                f.write('[[setting-{}-{}]]'.format(sectname, optname) + "\n")
                f.write("==== {}".format(optname) + "\n")
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
    return reversed(sorted(cnt, key=lambda k: cnt[k]))


def generate_manpage_author(f):
    """Generate the manpage AUTHOR section."""
    f.write("== AUTHOR\n")
    f.write("Contributors, sorted by the number of commits in descending "
            "order:\n\n")
    for author in _get_authors():
        f.write('* {}\n'.format(author))
    f.write('\n')


def generate_manpage_bugs(f):
    """Generate the manpage BUGS section."""
    f.write('== BUGS\n')
    f.write("Bugs are tracked at two locations:\n\n")
    f.write("* The link:BUGS[doc/BUGS] and link:TODO[doc/TODO] files shipped "
            "with qutebrowser.\n")
    f.write("* The Github issue tracker at https://github.com/The-Compiler/"
            "qutebrowser/issues .\n\n")
    f.write("If you found a bug or have a suggestion, either open a ticket "
            "in the github issue tracker, or write a mail to the "
            "https://lists.schokokeks.org/mailman/listinfo.cgi/qutebrowser["
            "mailinglist] at mailto:qutebrowser@lists.qutebrowser.org[].\n\n")


def generate_manpage_copyright(f):
    """Generate the COPYRIGHT section of the manpage."""
    f.write('== COPYRIGHT\n')
    f.write("This program is free software: you can redistribute it and/or "
            "modify it under the terms of the GNU General Public License as "
            "published by the Free Software Foundation, either version 3 of "
            "the License, or (at your option) any later version.\n\n")
    f.write("This program is distributed in the hope that it will be useful, "
            "but WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the "
            "GNU General Public License for more details.\n\n")
    f.write("You should have received a copy of the GNU General Public "
            "License along with this program.  If not, see "
            "<http://www.gnu.org/licenses/>.\n")


def generate_manpage_resources(f):
    """Generate the RESOURCES section of the manpage."""
    f.write('== RESOURCES\n\n')
    f.write("* Website: http://www.qutebrowser.org/\n")
    f.write("* Mailinglist: mailto:qutebrowser@lists.qutebrowser.org[] / "
            "https://lists.schokokeks.org/mailman/listinfo.cgi/qutebrowser\n")
    f.write("* IRC: irc://irc.freenode.org/#qutebrowser[`#qutebrowser`] on "
            "http://freenode.net/[Freenode]\n")
    f.write("* Github: https://github.com/The-Compiler/qutebrowser\n\n")


def regenerate_authors(filename):
    """Re-generate the authors inside README based on the commits made."""
    oshandle, tmpname = tempfile.mkstemp()
    with _open_file(filename, mode='r') as infile, \
            _open_file(oshandle, mode='w') as temp:
        ignore = False
        for line in infile:
            if line.strip() == '// QUTE_AUTHORS_START':
                ignore = True
                temp.write(line)
                for author in _get_authors():
                    temp.write('* {}\n'.format(author))
            elif line.strip() == '// QUTE_AUTHORS_END':
                temp.write(line)
                ignore = False
            elif not ignore:
                temp.write(line)
    os.remove(filename)
    shutil.move(tmpname, filename)


if __name__ == '__main__':
    with _open_file('doc/qutebrowser.1.asciidoc') as fobj:
        generate_manpage_header(fobj)
        generate_manpage_name(fobj)
        generate_manpage_synopsis(fobj)
        generate_manpage_description(fobj)
        generate_manpage_options(fobj)
        generate_settings(fobj)
        generate_commands(fobj)
        generate_manpage_bugs(fobj)
        generate_manpage_author(fobj)
        generate_manpage_resources(fobj)
        generate_manpage_copyright(fobj)
    regenerate_authors('README.asciidoc')
