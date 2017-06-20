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

"""Configuration data for config.py.

Module attributes:

FIRST_COMMENT: The initial comment header to place in the config.
SECTION_DESC: A dictionary with descriptions for sections.
DATA: A global read-only copy of the default config, an OrderedDict of
      sections.
"""

# FIXME:conf reintroduce interpolation?

import sys
import re
import collections
import functools

from qutebrowser.config import configtypes
from qutebrowser.utils import usertypes, qtutils, utils

DATA = None


FIRST_COMMENT = r"""
# vim: ft=dosini

# Configfile for qutebrowser.
#
# This configfile is parsed by python's configparser in extended
# interpolation mode. The format is very INI-like, so there are
# categories like [general] with "key = value"-pairs.
#
# Note that you shouldn't add your own comments, as this file is
# regenerated every time the config is saved.
#
# Interpolation looks like  ${value}  or  ${section:value} and will be
# replaced by the respective value.
#
# Some settings will expand environment variables. Note that, since
# interpolation is run first, you will need to escape the  $  char as
# described below.
#
# This is the default config, so if you want to remove anything from
# here (as opposed to change/add), for example a key binding, set it to
# an empty value.
#
# You will need to escape the following values:
#   - # at the start of the line (at the first position of the key) (\#)
#   - $ in a value ($$)
"""


DEFAULT_FONT_SIZE = '10pt' if sys.platform == 'darwin' else '8pt'
# FIXME:conf what to do about this?
MONOSPACE = (' xos4 Terminus, Terminus, Monospace, '
             '"DejaVu Sans Mono", Monaco, '
             '"Bitstream Vera Sans Mono", "Andale Mono", '
             '"Courier New", Courier, "Liberation Mono", '
             'monospace, Fixed, Consolas, Terminal')


Option = collections.namedtuple('Option', ['name', 'typ', 'default',
                                           'backends', 'description'])


def _raise_invalid_node(name, what, node):
    """Raise an exception for an invalid configdata YAML node.

    Args:
        name: The name of the setting being parsed.
        what: The name of the thing being parsed.
        node: The invalid node.
    """
    raise ValueError("Invalid node for {} while reading {}: {!r}".format(
        name, what, node))


def _parse_yaml_type(name, node):
    if isinstance(node, str):
        # e.g:
        #  type: Bool
        # -> create the type object without any arguments
        type_name = node
        kwargs = {}
    elif isinstance(node, dict):
        # e.g:
        #  type:
        #    name: String
        #    none_ok: true
        # -> create the type object and pass arguments
        type_name = node.pop('name')
        kwargs = node
        valid_values = kwargs.get('valid_values', None)
        if valid_values is not None:
            kwargs['valid_values'] = configtypes.ValidValues(*valid_values)
    else:
        _raise_invalid_node(name, 'type', node)

    try:
        typ = getattr(configtypes, type_name)
    except AttributeError as e:
        raise AttributeError("Did not find type {} for {}".format(
            type_name, name))

    # Parse sub-types
    try:
        if typ is configtypes.Dict:
            kwargs['keytype'] = _parse_yaml_type(name, kwargs['keytype'])
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
        elif typ is configtypes.List:
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
    except KeyError as e:
        _raise_invalid_node(name, str(e), node)

    try:
        return typ(**kwargs)
    except TypeError as e:
        raise TypeError("Error while creating {} with {}: {}".format(
            type_name, node, e))


def _parse_yaml_backends_dict(name, node):
    """Parse a dict definition for backends.

    Example:

    backends:
      QtWebKit: true
      QtWebEngine: Qt 5.9
    """
    str_to_backend = {
        'QtWebKit': usertypes.Backend.QtWebKit,
        'QtWebEngine': usertypes.Backend.QtWebEngine,
    }

    if node.keys() != str_to_backend.keys():
        _raise_invalid_node(name, 'backends', node)

    backends = []

    # The value associated to the key, and whether we should add that backend
    # or not.
    conditionals = {
        True: True,
        False: False,
        'Qt 5.8': qtutils.version_check('5.8'),
        'Qt 5.9': qtutils.version_check('5.9'),
    }
    for key in node.keys():
        if conditionals[node[key]]:
            backends.append(str_to_backend[key])

    return backends


def _parse_yaml_backends(name, node):
    """Parse a backend node in the yaml.

    It can have one of those four forms:
    - Not present -> setting applies to both backends.
    - backend: QtWebKit -> setting only available with QtWebKit
    - backend: QtWebEngine -> setting only available with QtWebEngine
    - backend:
       QtWebKit: true
       QtWebEngine: Qt 5.9
      -> setting available based on the given conditionals.
    """
    if node is None:
        return [usertypes.Backend.QtWebKit, usertypes.Backend.QtWebEngine]
    elif node == 'QtWebKit':
        return [usertypes.Backend.QtWebKit]
    elif node == 'QtWebEngine':
        return [usertypes.Backend.QtWebEngine]
    elif isinstance(node, dict):
        return _parse_yaml_backends_dict(name, node)
    _raise_invalid_node(name, 'backends', node)


def _read_yaml(yaml_data):
    """Read config data from a YAML file.

    Args:
        yaml_data: The YAML string to parse.

    Return:
        A dict mapping option names to Option elements.
    """
    parsed = {}
    data = utils.yaml_load(yaml_data)

    keys = {'type', 'default', 'desc', 'backend'}

    for name, option in data.items():
        if not set(option.keys()).issubset(keys):
            raise ValueError("Invalid keys {} for {}".format(
                option.keys(), name))

        parsed[name] = Option(
            name=name,
            typ=_parse_yaml_type(name, option['type']),
            default=option['default'],
            backends=_parse_yaml_backends(name, option.get('backend', None)),
            description=option['desc'])

    # Make sure no key shadows another.
    for key1 in parsed:
        for key2 in parsed:
            if key2.startswith(key1 + '.'):
                raise ValueError("Shadowing keys {} and {}".format(key1, key2))

    return parsed


@functools.lru_cache(maxsize=256)
def is_valid_prefix(prefix):
    """Check whether the given prefix is a valid prefix for some option."""
    return any(key.startswith(prefix + '.') for key in DATA)


def init():
    """Initialize configdata from the YAML file."""
    global DATA
    DATA = _read_yaml(utils.read_file('config/configdata.yml'))
