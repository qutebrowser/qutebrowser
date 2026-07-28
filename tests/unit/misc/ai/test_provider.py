# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.ai.provider."""

import json
from unittest import mock

import pytest

from qutebrowser.misc.ai import provider
from qutebrowser.misc.ai.types import CandidateCommand, ResolvedCommand

# Re-usable mock for _chat_completion dict return.
_MOCK_MSG = {'content': ''}


@pytest.fixture
def sample_candidates():
    """A small set of candidate commands."""
    return [
        CandidateCommand(name='tab-close', description='Close tab'),
        CandidateCommand(name='tab-mute', description='Mute tab'),
        CandidateCommand(name='reload', description='Reload page'),
    ]


class TestParseLLMResponse:

    """Tests for _parse_llm_response."""

    def test_well_formed_json(self):
        """Well-formed JSON is parsed correctly."""
        valid_names = {'tab-close', 'tab-mute'}
        content = json.dumps([
            {'command': 'tab-close', 'args': []},
            {'command': 'tab-mute', 'args': ['--all']},
        ])
        result = provider._parse_llm_response(content, valid_names)
        assert len(result) == 2
        assert result[0] == ResolvedCommand(command='tab-close', args=[])
        assert result[1] == ResolvedCommand(command='tab-mute',
                                            args=['--all'])

    def test_malformed_json(self):
        """Malformed JSON does not crash and returns empty list."""
        result = provider._parse_llm_response(
            'not valid json at all', {'tab-close'},
        )
        assert result == []

    def test_hallucinated_command_dropped(self):
        """A hallucinated command outside the candidate set is dropped."""
        valid_names = {'tab-close'}
        content = json.dumps([
            {'command': 'tab-close', 'args': []},
            {'command': 'non-existent-command', 'args': []},
        ])
        result = provider._parse_llm_response(content, valid_names)
        assert len(result) == 1
        assert result[0].command == 'tab-close'

    def test_empty_response(self):
        """Empty list response is handled."""
        result = provider._parse_llm_response('[]', {'tab-close'})
        assert result == []

    def test_markdown_fences_stripped(self):
        """Markdown fences around JSON are stripped before parsing."""
        valid_names = {'tab-close'}
        content = "```json\n[{\"command\": \"tab-close\", \"args\": []}]\n```"
        result = provider._parse_llm_response(content, valid_names)
        assert len(result) == 1
        assert result[0].command == 'tab-close'


class TestMockTranslate:

    """Tests for _mock_translate (deterministic fallback)."""

    def test_returns_top_candidate(self, sample_candidates):
        """Mock returns top candidate (first in list) with no args."""
        result = provider._mock_translate(
            'close tab', sample_candidates,
        )
        assert len(result) == 1
        assert result[0] == ResolvedCommand(command='tab-close', args=[])

    def test_empty_candidates(self):
        """Empty candidates returns empty result."""
        result = provider._mock_translate('close tab', [])
        assert result == []


class TestTranslate:

    """Tests for provider.translate (integration with HTTP + fallback)."""

    @mock.patch.object(provider, '_chat_completion')
    def test_connection_failure_triggers_mock(
        self, mock_chat, sample_candidates,
    ):
        """When the LLM call fails, the mock provider path is used."""
        mock_chat.return_value = None
        with mock.patch.object(provider, '_mock_translate') as mock_mock:
            mock_mock.return_value = [
                ResolvedCommand(command='tab-close', args=[]),
            ]
            result = provider.translate('close tab', sample_candidates)
            assert len(result) == 1
            assert result[0].command == 'tab-close'
            mock_mock.assert_called_once_with(
                'close tab', sample_candidates,
            )

    @mock.patch.object(provider, '_chat_completion')
    def test_successful_llm_response(
        self, mock_chat, sample_candidates,
    ):
        """A successful LLM response is parsed and returned."""
        mock_chat.return_value = {'content': json.dumps([
            {'command': 'tab-mute', 'args': ['--all']},
        ])}
        result = provider.translate('mute all', sample_candidates)
        assert len(result) == 1
        assert result[0] == ResolvedCommand(
            command='tab-mute', args=['--all'],
        )

    @mock.patch.object(provider, '_chat_completion')
    def test_all_hallucinated_falls_back_to_mock(
        self, mock_chat, sample_candidates,
    ):
        """When LLM returns only hallucinated commands, mock is used."""
        mock_chat.return_value = {'content': json.dumps([
            {'command': 'fake-command', 'args': []},
        ])}
        result = provider.translate('close tab', sample_candidates)
        # Should fall back to mock since all were hallucinated
        assert len(result) >= 1
