# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.ai.translator."""

from unittest import mock

import pytest

from qutebrowser.misc.ai import translator
from qutebrowser.misc.ai.types import CandidateCommand, ResolvedCommand


class TestTranslateQuery:

    """Tests for translator.translate_query()."""

    def test_empty_corpus(self):
        """When the corpus is empty, an empty string is returned."""
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=[],
        ):
            result = translator.translate_query('close tab')
        assert result == ''

    def test_no_candidates(self):
        """When retrieval returns nothing, an empty string is returned."""
        corpus = [CandidateCommand(name='tab-close', description='')]
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=[],
            ):
                result = translator.translate_query('xyzzy')
        assert result == ''

    def test_single_command(self):
        """A single resolved command is returned as-is."""
        corpus = [
            CandidateCommand(name='tab-close', description='Close tab'),
        ]
        candidates = [
            CandidateCommand(name='tab-close', description='Close tab'),
        ]
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=candidates,
            ):
                with mock.patch(
                    'qutebrowser.misc.ai.translator.provider.translate',
                    return_value=[
                        ResolvedCommand(command='tab-close', args=[]),
                    ],
                ):
                    result = translator.translate_query('close tab')
        assert result == 'tab-close'

    def test_multi_command_join(self):
        """Multiple resolved commands are joined with ';;'."""
        corpus = [
            CandidateCommand(name='tab-close', description='Close tab'),
            CandidateCommand(
                name='tab-mute', description='Mute tab',
                args=[{'name': 'all', 'long_flag': '--all', 'arg_type': 'flag'}],
            ),
            CandidateCommand(name='reload', description='Reload'),
        ]
        candidates = corpus
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=candidates,
            ):
                with mock.patch(
                    'qutebrowser.misc.ai.translator.provider.translate',
                    return_value=[
                        ResolvedCommand(command='tab-close', args=[]),
                        ResolvedCommand(command='tab-mute', args=['--all']),
                    ],
                ):
                    result = translator.translate_query(
                        'close all tabs except this and mute',
                    )
        assert result == 'tab-close ;; tab-mute --all'

    def test_hallucinated_command_dropped(self):
        """Command names not in the candidate set are dropped."""
        corpus = [
            CandidateCommand(name='reload', description='Reload'),
        ]
        candidates = corpus
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=candidates,
            ):
                with mock.patch(
                    'qutebrowser.misc.ai.translator.provider.translate',
                    return_value=[
                        ResolvedCommand(command='reload', args=[]),
                        ResolvedCommand(command='fake-cmd', args=[]),
                    ],
                ):
                    result = translator.translate_query('reload')
        assert result == 'reload'

    def test_all_hallucinated_returns_empty(self):
        """When all commands are hallucinated, empty string is returned."""
        corpus = [
            CandidateCommand(name='reload', description='Reload'),
        ]
        candidates = corpus
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=candidates,
            ):
                with mock.patch(
                    'qutebrowser.misc.ai.translator.provider.translate',
                    return_value=[
                        ResolvedCommand(command='fake-cmd', args=[]),
                    ],
                ):
                    result = translator.translate_query('reload')
        assert result == ''

    def test_args_included_in_command_string(self):
        """Args are appended to the command string."""
        corpus = [
            CandidateCommand(
                name='tab-close', description='Close tab',
                args=[{'name': 'except-current', 'long_flag': '--except-current',
                       'arg_type': 'flag'}],
            ),
        ]
        candidates = corpus
        with mock.patch(
            'qutebrowser.misc.ai.translator.registry.get_corpus',
            return_value=corpus,
        ):
            with mock.patch(
                'qutebrowser.misc.ai.translator.retrieval.retrieve',
                return_value=candidates,
            ):
                with mock.patch(
                    'qutebrowser.misc.ai.translator.provider.translate',
                    return_value=[
                        ResolvedCommand(
                            command='tab-close', args=['--except-current'],
                        ),
                    ],
                ):
                    result = translator.translate_query(
                        'close all tabs except this one',
                    )
        assert result == 'tab-close --except-current'
