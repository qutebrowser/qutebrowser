# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.ai.registry."""

from unittest import mock

import pytest

from qutebrowser.misc.ai import registry
from qutebrowser.misc.ai.types import CandidateCommand


def _make_fake_command(name, desc, pos_args=None, opt_args=None):
    """Build a fake Command-like object."""
    cmd = mock.Mock(spec=['name', 'desc', 'opt_args', 'pos_args'])
    cmd.name = name
    cmd.desc = desc
    cmd.opt_args = opt_args or {}
    cmd.pos_args = pos_args or []
    return cmd


class TestGetCorpus:

    """Tests for registry.get_corpus()."""

    def test_empty_registry(self):
        """An empty command registry yields an empty corpus."""
        with mock.patch('qutebrowser.misc.ai.registry.objects.commands', {}):
            result = registry.get_corpus()
        assert result == []

    def test_single_command(self):
        """A single command is correctly extracted."""
        fake_cmds = {
            'tab-close': _make_fake_command(
                'tab-close',
                'Close the current tab',
                pos_args=[('count', 'count')],
            ),
        }
        with mock.patch('qutebrowser.misc.ai.registry.objects.commands',
                        fake_cmds):
            result = registry.get_corpus()

        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry, CandidateCommand)
        assert entry.name == 'tab-close'
        assert entry.description == 'Close the current tab'
        assert len(entry.args) == 1
        assert entry.args[0]['name'] == 'count'
        assert entry.args[0]['required'] is True

    def test_command_with_optional_args(self):
        """Optional (flag) arguments are included in the arg list."""
        fake_cmds = {
            'tab-mute': _make_fake_command(
                'tab-mute',
                'Mute/unmute tabs',
                opt_args={'all': ('--all', '-a')},
            ),
        }
        with mock.patch('qutebrowser.misc.ai.registry.objects.commands',
                        fake_cmds):
            result = registry.get_corpus()

        assert len(result) == 1
        entry = result[0]
        assert entry.name == 'tab-mute'
        assert len(entry.args) == 1
        assert entry.args[0]['name'] == 'all'
        assert entry.args[0]['flag'] == '-a'
        assert entry.args[0]['required'] is False

    def test_multiple_commands(self):
        """Multiple commands are all present in the corpus."""
        fake_cmds = {
            'reload': _make_fake_command('reload', 'Reload the page'),
            'zoom-in': _make_fake_command('zoom-in', 'Zoom in'),
        }
        with mock.patch('qutebrowser.misc.ai.registry.objects.commands',
                        fake_cmds):
            result = registry.get_corpus()

        assert len(result) == 2
        names = {e.name for e in result}
        assert names == {'reload', 'zoom-in'}
