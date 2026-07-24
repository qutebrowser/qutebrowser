# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.ai.retrieval."""

import pytest

from qutebrowser.misc.ai import retrieval
from qutebrowser.misc.ai.types import CandidateCommand


@pytest.fixture
def sample_corpus():
    """A small fixed corpus for retrieval tests."""
    return [
        CandidateCommand(
            name='tab-close',
            description='Close the current tab',
            args=[],
        ),
        CandidateCommand(
            name='tab-mute',
            description='Mute/unmute tabs',
            args=[],
        ),
        CandidateCommand(
            name='reload',
            description='Reload the current page',
            args=[],
        ),
        CandidateCommand(
            name='zoom-in',
            description='Zoom in on the page',
            args=[],
        ),
        CandidateCommand(
            name='open',
            description='Open a URL or file',
            args=[{'name': 'url', 'required': True}],
        ),
    ]


class TestFallbackRetrieval:

    """Tests for the TF-IDF fallback path (always runs)."""

    def test_empty_corpus(self):
        """An empty corpus returns an empty list."""
        result = retrieval.retrieve('close tab', [], k=5)
        assert result == []

    def test_relevant_command_ranked_first(self, sample_corpus):
        """The most relevant command should be ranked first."""
        result = retrieval.retrieve('close tab', sample_corpus, k=5)
        assert len(result) > 0
        # 'tab-close' should be the most relevant for "close tab"
        assert result[0].name == 'tab-close'

    def test_relevant_command_mute(self, sample_corpus):
        """Mute-related query should rank tab-mute first."""
        result = retrieval.retrieve('mute tab', sample_corpus, k=5)
        assert len(result) > 0
        assert result[0].name == 'tab-mute'

    def test_relevant_command_open(self, sample_corpus):
        """Open-related query should rank open first."""
        result = retrieval.retrieve('open url', sample_corpus, k=5)
        assert len(result) > 0
        assert result[0].name == 'open'

    def test_top_k_filter(self, sample_corpus):
        """Only the top-k results are returned."""
        result = retrieval.retrieve('tab', sample_corpus, k=2)
        assert len(result) <= 2

    def test_scores_decreasing(self, sample_corpus):
        """Scores should be in decreasing order."""
        scores = retrieval._retrieve_tfidf(
            'close tab', sample_corpus,
        )
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: -x[1])
        for i in range(len(indexed) - 1):
            assert indexed[i][1] >= indexed[i + 1][1]
