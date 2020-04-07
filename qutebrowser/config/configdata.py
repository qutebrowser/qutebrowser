# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

DATA: A dict of Option objects after init() has been called.
"""

import typing
from typing import Optional
import functools

import attr
from qutebrowser.config import configtypes
from qutebrowser.utils import usertypes, qtutils, utils
from qutebrowser.misc import debugcachestats

DATA = typing.cast(typing.Mapping[str, 'Option'], None)
MIGRATIONS = typing.cast('Migrations', None)

_BackendDict = typing.Mapping[str, typing.Union[str, bool]]


@attr.s
class Option:

    """Description of an Option in the config.

    Note that this is just an option which exists, with no value associated.
    """

    name = attr.ib()  # type: str
    typ = attr.ib()  # type: configtypes.BaseType
    default = attr.ib()  # type: typing.Any
    backends = attr.ib()  # type: typing.Iterable[usertypes.Backend]
    raw_backends = attr.ib()  # type: Optional[typing.Mapping[str, bool]]
    description = attr.ib()  # type: str
    supports_pattern = attr.ib(default=False)  # type: bool
    restart = attr.ib(default=False)  # type: bool
    no_autoconfig = attr.ib(default=False)  # type: bool


@attr.s
class Migrations:

    """Migrated options in configdata.yml.

    Attributes:
        renamed: A dict mapping old option names to new names.
        deleted: A list of option names which have been removed.
    """

    renamed = attr.ib(
        default=attr.Factory(dict))  # type: typing.Dict[str, str]
    deleted = attr.ib(
        default=attr.Factory(list))  # type: typing.List[str]


def _raise_invalid_node(name: str, what: str, node: typing.Any) -> None:
    """Raise an exception for an invalid configdata YAML node.

    Args:
        name: The name of the setting being parsed.
        what: The name of the thing being parsed.
        node: The invalid node.
    """
    raise ValueError("Invalid node for {} while reading {}: {!r}".format(
        name, what, node))


def _parse_yaml_type(
        name: str,
        node: typing.Union[str, typing.Mapping[str, typing.Any]],
) -> configtypes.BaseType:
    if isinstance(node, str):
        # e.g:
        #   > type: Bool
        # -> create the type object without any arguments
        type_name = node
        kwargs = {}  # type: typing.MutableMapping[str, typing.Any]
    elif isinstance(node, dict):
        # e.g:
        #   > type:
        #   >   name: String
        #   >   none_ok: true
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
    except AttributeError:
        raise AttributeError("Did not find type {} for {}".format(
            type_name, name))

    # Parse sub-types
    try:
        if typ is configtypes.Dict:
            kwargs['keytype'] = _parse_yaml_type(name, kwargs['keytype'])
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
        elif typ is configtypes.List or typ is configtypes.ListOrValue:
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
    except KeyError as e:
        _raise_invalid_node(name, str(e), node)

    try:
        return typ(**kwargs)
    except TypeError as e:
        raise TypeError("Error while creating {} with {}: {}".format(
            type_name, node, e))


def _parse_yaml_backends_dict(
        name: str,
        node: _BackendDict,
) -> typing.Sequence[usertypes.Backend]:
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
        'Qt 5.9.2': qtutils.version_check('5.9.2'),
        'Qt 5.10': qtutils.version_check('5.10'),
        'Qt 5.11': qtutils.version_check('5.11'),
        'Qt 5.12': qtutils.version_check('5.12'),
        'Qt 5.13': qtutils.version_check('5.13'),
        'Qt 5.14': qtutils.version_check('5.14'),
    }
    for key in sorted(node.keys()):
        if conditionals[node[key]]:
            backends.append(str_to_backend[key])

    return backends


def _parse_yaml_backends(
        name: str,
        node: typing.Union[None, str, _BackendDict],
) -> typing.Sequence[usertypes.Backend]:
    """Parse a backend node in the yaml.

    It can have one of those four forms:
    - Not present -> setting applies to both backends.
    - backend: QtWebKit -> setting only available with QtWebKit
    - backend: QtWebEngine -> setting only available with QtWebEngine
    - backend:
       QtWebKit: true
       QtWebEngine: Qt 5.9
      -> setting available based on the given conditionals.

    Return:
        A list of backends.
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
    raise utils.Unreachable


def _read_yaml(
        yaml_data: str,
) -> typing.Tuple[typing.Mapping[str, Option], Migrations]:
    """Read config data from a YAML file.

    Args:
        yaml_data: The YAML string to parse.

    Return:
        A tuple with two elements:
            - A dict mapping option names to Option elements.
            - A Migrations object.
    """
    parsed = {}
    migrations = Migrations()
    data = utils.yaml_load(yaml_data)

    keys = {'type', 'default', 'desc', 'backend', 'restart',
            'supports_pattern', 'no_autoconfig'}

    for name, option in data.items():
        if set(option.keys()) == {'renamed'}:
            migrations.renamed[name] = option['renamed']
            continue
        if set(option.keys()) == {'deleted'}:
            value = option['deleted']
            if value is not True:
                raise ValueError("Invalid deleted value: {}".format(value))
            migrations.deleted.append(name)
            continue

        if not set(option.keys()).issubset(keys):
            raise ValueError("Invalid keys {} for {}".format(
                option.keys(), name))

        backends = option.get('backend', None)

        parsed[name] = Option(
            name=name,
            typ=_parse_yaml_type(name, option['type']),
            default=option['default'],
            backends=_parse_yaml_backends(name, backends),
            raw_backends=backends if isinstance(backends, dict) else None,
            description=option['desc'],
            restart=option.get('restart', False),
            supports_pattern=option.get('supports_pattern', False),
            no_autoconfig=option.get('no_autoconfig', False),
        )

    # Make sure no key shadows another.
    for key1 in parsed:
        for key2 in parsed:
            if key2.startswith(key1 + '.'):
                raise ValueError("Shadowing keys {} and {}".format(key1, key2))

    # Make sure rename targets actually exist.
    for old, new in migrations.renamed.items():
        if new not in parsed:
            raise ValueError("Renaming {} to unknown {}".format(old, new))

    return parsed, migrations


@debugcachestats.register()
@functools.lru_cache(maxsize=256)
def is_valid_prefix(prefix: str) -> bool:
    """Check whether the given prefix is a valid prefix for some option."""
    return any(key.startswith(prefix + '.') for key in DATA)


def init() -> None:
    """Initialize configdata from the YAML file."""
    global DATA, MIGRATIONS
    DATA, MIGRATIONS = _read_yaml(utils.read_file('config/configdata.yml'))
