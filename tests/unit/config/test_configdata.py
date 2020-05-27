# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configdata."""

import textwrap

import yaml
import pytest

# To run cmdutils.register decorators
from qutebrowser import app  # pylint: disable=unused-import
from qutebrowser.config import configdata, configtypes
from qutebrowser.utils import usertypes


def test_init(config_stub):
    """Test reading the default yaml file."""
    # configdata.init() is called by config_stub
    config_stub.val.aliases = {}
    assert isinstance(configdata.DATA, dict)
    assert 'search.ignore_case' in configdata.DATA


def test_data(config_stub):
    """Test various properties of the default values."""
    for option in configdata.DATA.values():
        # Make sure to_py and to_str work
        option.typ.to_py(option.default)
        option.typ.to_str(option.default)

        # https://github.com/qutebrowser/qutebrowser/issues/3104
        # For lists/dicts, don't use None as default
        if isinstance(option.typ, (configtypes.Dict, configtypes.List)):
            assert option.default is not None, option
        # For ListOrValue, use a list as default
        if isinstance(option.typ, configtypes.ListOrValue):
            assert isinstance(option.default, list), option

        # Make sure floats also have floats for defaults/bounds
        if isinstance(option.typ, configtypes.Float):
            for value in [option.default,
                          option.typ.minval,
                          option.typ.maxval]:
                assert value is None or isinstance(value, float), option

        # No double spaces after dots
        assert '.  ' not in option.description, option


def test_init_benchmark(benchmark):
    benchmark(configdata.init)


def test_is_valid_prefix(monkeypatch):
    monkeypatch.setattr(configdata, 'DATA', ['foo.bar'])
    assert configdata.is_valid_prefix('foo')
    assert not configdata.is_valid_prefix('foo.bar')
    assert not configdata.is_valid_prefix('foa')


class TestReadYaml:

    def test_valid(self):
        yaml_data = textwrap.dedent("""
            test1:
                type: Bool
                default: true
                desc: Hello World

            test2:
                type: String
                default: foo
                backend: QtWebKit
                desc: Hello World 2
        """)
        data, _migrations = configdata._read_yaml(yaml_data)
        assert data.keys() == {'test1', 'test2'}
        assert data['test1'].description == "Hello World"
        assert data['test2'].default == "foo"
        assert data['test2'].backends == [usertypes.Backend.QtWebKit]
        assert isinstance(data['test1'].typ, configtypes.Bool)

    def test_invalid_keys(self):
        """Test reading with unknown keys."""
        data = textwrap.dedent("""
            test:
                type: Bool
                default: true
                desc: Hello World
                hello: world
        """,)
        with pytest.raises(ValueError, match='Invalid keys'):
            configdata._read_yaml(data)

    @pytest.mark.parametrize('first, second, shadowing', [
        ('foo', 'foo.bar', True),
        ('foo.bar', 'foo', True),
        ('foo.bar', 'foo.bar.baz', True),
        ('foo.bar', 'foo.baz', False),
    ])
    def test_shadowing(self, first, second, shadowing):
        """Make sure a setting can't shadow another."""
        data = textwrap.dedent("""
            {first}:
                type: Bool
                default: true
                desc: Hello World

            {second}:
                type: Bool
                default: true
                desc: Hello World
        """.format(first=first, second=second))
        if shadowing:
            with pytest.raises(ValueError, match='Shadowing keys'):
                configdata._read_yaml(data)
        else:
            configdata._read_yaml(data)

    def test_rename(self):
        yaml_data = textwrap.dedent("""
            test:
                renamed: test_new

            test_new:
                type: Bool
                default: true
                desc: Hello World
        """)
        data, migrations = configdata._read_yaml(yaml_data)
        assert data.keys() == {'test_new'}
        assert migrations.renamed == {'test': 'test_new'}

    def test_rename_unknown_target(self):
        yaml_data = textwrap.dedent("""
            test:
                renamed: test2
        """)
        with pytest.raises(ValueError, match='Renaming test to unknown test2'):
            configdata._read_yaml(yaml_data)

    def test_delete(self):
        yaml_data = textwrap.dedent("""
            test:
                deleted: true
        """)
        data, migrations = configdata._read_yaml(yaml_data)
        assert not data.keys()
        assert migrations.deleted == ['test']

    def test_delete_invalid_value(self):
        yaml_data = textwrap.dedent("""
            test:
                deleted: false
        """)
        with pytest.raises(ValueError, match='Invalid deleted value: False'):
            configdata._read_yaml(yaml_data)


class TestParseYamlType:

    def _yaml(self, s):
        """Get the type from parsed YAML data."""
        return yaml.safe_load(textwrap.dedent(s))['type']

    def test_simple(self):
        """Test type which is only a name."""
        data = self._yaml("type: Bool")
        typ = configdata._parse_yaml_type('test', data)
        assert isinstance(typ, configtypes.Bool)
        assert not typ.none_ok

    def test_complex(self):
        """Test type parsing with arguments."""
        data = self._yaml("""
            type:
              name: String
              minlen: 2
        """)
        typ = configdata._parse_yaml_type('test', data)
        assert isinstance(typ, configtypes.String)
        assert not typ.none_ok
        assert typ.minlen == 2

    def test_list(self):
        """Test type parsing with a list and subtypes."""
        data = self._yaml("""
            type:
              name: List
              valtype: String
        """)
        typ = configdata._parse_yaml_type('test', data)
        assert isinstance(typ, configtypes.List)
        assert isinstance(typ.valtype, configtypes.String)
        assert not typ.none_ok
        assert not typ.valtype.none_ok

    def test_dict(self):
        """Test type parsing with a dict and subtypes."""
        data = self._yaml("""
            type:
              name: Dict
              keytype: String
              valtype:
                name: Int
                minval: 10
        """)
        typ = configdata._parse_yaml_type('test', data)
        assert isinstance(typ, configtypes.Dict)
        assert isinstance(typ.keytype, configtypes.String)
        assert isinstance(typ.valtype, configtypes.Int)
        assert not typ.none_ok
        assert typ.valtype.minval == 10

    def test_invalid_node(self):
        """Test type parsing with invalid node type."""
        data = self._yaml("type: 42")
        with pytest.raises(ValueError, match="Invalid node for test while "
                                             "reading type: 42"):
            configdata._parse_yaml_type('test', data)

    def test_unknown_type(self):
        """Test type parsing with type which doesn't exist."""
        data = self._yaml("type: Foobar")
        with pytest.raises(AttributeError,
                           match="Did not find type Foobar for test"):
            configdata._parse_yaml_type('test', data)

    def test_unknown_dict(self):
        """Test type parsing with a dict without keytype."""
        data = self._yaml("type: Dict")
        with pytest.raises(ValueError, match="Invalid node for test while "
                                             "reading 'keytype': 'Dict'"):
            configdata._parse_yaml_type('test', data)

    def test_unknown_args(self):
        """Test type parsing with unknown type arguments."""
        data = self._yaml("""
            type:
              name: Int
              answer: 42
        """)
        with pytest.raises(TypeError, match="Error while creating Int"):
            configdata._parse_yaml_type('test', data)


class TestParseYamlBackend:

    def _yaml(self, s):
        """Get the type from parsed YAML data."""
        return yaml.safe_load(textwrap.dedent(s))['backend']

    @pytest.mark.parametrize('backend, expected', [
        ('QtWebKit', [usertypes.Backend.QtWebKit]),
        ('QtWebEngine', [usertypes.Backend.QtWebEngine]),
        # This is also what _parse_yaml_backends gets when backend: is not
        # given at all
        ('null', [usertypes.Backend.QtWebKit, usertypes.Backend.QtWebEngine]),
    ])
    def test_simple(self, backend, expected):
        """Check a simple "backend: QtWebKit"."""
        data = self._yaml("backend: {}".format(backend))
        backends = configdata._parse_yaml_backends('test', data)
        assert backends == expected

    @pytest.mark.parametrize('webkit, has_new_version, expected', [
        (True, True, [usertypes.Backend.QtWebEngine,
                      usertypes.Backend.QtWebKit]),
        (False, True, [usertypes.Backend.QtWebEngine]),
        (True, False, [usertypes.Backend.QtWebKit]),
    ])
    def test_dict(self, monkeypatch, webkit, has_new_version, expected):
        data = self._yaml("""
            backend:
              QtWebKit: {}
              QtWebEngine: Qt 5.8
        """.format('true' if webkit else 'false'))
        monkeypatch.setattr(configdata.qtutils, 'version_check',
                            lambda v: has_new_version)
        backends = configdata._parse_yaml_backends('test', data)
        assert backends == expected

    @pytest.mark.parametrize('yaml_data', [
        # Wrong type
        "backend: 42",
        # Unknown key
        """
        backend:
          QtWebKit: true
          QtWebEngine: true
          foo: bar
        """,
        # Missing key
        """
        backend:
          QtWebKit: true
        """,
    ])
    def test_invalid_backend(self, yaml_data):
        with pytest.raises(ValueError, match="Invalid node for test while "
                                             "reading backends:"):
            configdata._parse_yaml_backends('test', self._yaml(yaml_data))
