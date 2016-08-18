# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities related to javascript interaction."""


def string_escape(text):
    """Escape values special to javascript in strings.

    With this we should be able to use something like:
      elem.evaluateJavaScript("this.value='{}'".format(string_escape(...)))
    And all values should work.
    """
    # This is a list of tuples because order matters, and using OrderedDict
    # makes no sense because we don't actually need dict-like properties.
    replacements = (
        ('\\', r'\\'),  # First escape all literal \ signs as \\.
        ("'", r"\'"),   # Then escape ' and " as \' and \".
        ('"', r'\"'),   # (note it won't hurt when we escape the wrong one).
        ('\n', r'\n'),  # We also need to escape newlines for some reason.
        ('\r', r'\r'),
        ('\x00', r'\x00'),
        ('\ufeff', r'\ufeff'),
        # http://stackoverflow.com/questions/2965293/
        ('\u2028', r'\u2028'),
        ('\u2029', r'\u2029'),
    )
    for orig, repl in replacements:
        text = text.replace(orig, repl)
    return text


def _convert_js_arg(arg):
    """Convert the given argument so it's the equivalent in JS."""
    if arg is None:
        return 'undefined'
    elif isinstance(arg, str):
        return '"{}"'.format(string_escape(arg))
    elif isinstance(arg, bool):
        return str(arg).lower()
    elif isinstance(arg, (int, float)):
        return str(arg)
    else:
        raise TypeError("Don't know how to handle {!r} of type {}!".format(
            arg, type(arg).__name__))


def assemble(module, function, *args):
    """Assemble a javascript file and a function call."""
    js_args = ', '.join(_convert_js_arg(arg) for arg in args)
    if module == 'window':
        parts = ['window', function]
    else:
        parts = ['window', '_qutebrowser', module, function]
    code = '"use strict";\n{}({});'.format('.'.join(parts), js_args)
    return code
