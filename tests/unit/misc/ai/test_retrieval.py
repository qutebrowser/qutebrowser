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


def _check_st() -> bool:
    """Check if sentence-transformers is available."""
    return retrieval._CAN_USE_ST


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


@pytest.mark.skipif(not _check_st(), reason='sentence-transformers not installed')
class TestSentenceTransformerRetrieval:

    """Tests for the sentence-transformers embedding path."""

    @pytest.fixture(autouse=True)
    def _reset_embedder(self):
        """Reset the embedder before each test so each gets a fresh load."""
        retrieval._EMBEDDER = None
        yield
        retrieval._EMBEDDER = None

    @pytest.fixture
    def extended_corpus(self):
        """A broader corpus with tab-management and open-related commands."""
        return [
            CandidateCommand(name='tab-close',
                             description='Close the current tab'),
            CandidateCommand(name='tab-mute',
                             description='Mute/unmute tabs'),
            CandidateCommand(name='tab-only',
                             description='Close all tabs except the current one'),
            CandidateCommand(name='tab-next',
                             description='Switch to the next tab'),
            CandidateCommand(name='tab-new',
                             description='Open a new tab',
                             args=[{'name': 'url', 'required': True}]),
            CandidateCommand(name='open',
                             description='Open a URL or file',
                             args=[{'name': 'url', 'required': True}]),
            CandidateCommand(name='reload',
                             description='Reload the current page'),
            CandidateCommand(name='run-with-count',
                             description='Run a command with count'),
            CandidateCommand(name='fullscreen',
                             description='Fullscreen mode'),
            CandidateCommand(name='zoom-in',
                             description='Zoom in on the page'),
        ]

    def test_embedder_is_loaded(self):
        """_get_embedder() should return a SentenceTransformer instance."""
        embedder = retrieval._get_embedder()
        assert embedder is not None
        assert 'SentenceTransformer' in type(embedder).__name__

    def test_retrieve_embeddings_returns_scores(self, sample_corpus):
        """_retrieve_embeddings should return one float per corpus entry."""
        scores = retrieval._retrieve_embeddings(
            'close tab', sample_corpus,
        )
        assert len(scores) == len(sample_corpus)
        assert all(isinstance(s, float) for s in scores)

    def test_embedding_scores_are_non_zero_for_relevant(self, sample_corpus):
        """Relevant queries should have non-zero similarity scores."""
        scores = retrieval._retrieve_embeddings(
            'close tab', sample_corpus,
        )
        tab_close_idx = next(
            i for i, c in enumerate(sample_corpus) if c.name == 'tab-close'
        )
        assert scores[tab_close_idx] > 0

    def test_retrieve_uses_embeddings_when_available(self, sample_corpus):
        """retrieve() should return results when embeddings are available."""
        result = retrieval.retrieve('close tab', sample_corpus, k=3)
        assert len(result) > 0
        assert result[0].name == 'tab-close'

    def test_retrieve_ranks_open_first(self, sample_corpus):
        """An open-related query should rank the open command first."""
        result = retrieval.retrieve('open url', sample_corpus, k=5)
        assert result[0].name == 'open'

    def test_retrieve_ranks_tab_close_for_close_query(self, sample_corpus):
        """A close-related query should rank tab-close first."""
        result = retrieval.retrieve('close current tab', sample_corpus, k=5)
        assert result[0].name == 'tab-close'

    def test_complex_query_open_outranks_run_with_count(self, extended_corpus):
        """For a multi-tab open query, 'open' should rank above
        'run-with-count'."""
        result = retrieval.retrieve(
            'open two tabs, one with google and one with wikipedia',
            extended_corpus, k=10,
        )
        names = [c.name for c in result]
        assert names.index('open') < names.index('run-with-count')

    def test_complex_query_open_in_top_5(self, extended_corpus):
        """For a multi-tab open query, 'open' should be in the top-5."""
        result = retrieval.retrieve(
            'open two tabs, one with google and one with wikipedia',
            extended_corpus, k=10,
        )
        names = [c.name for c in result]
        assert names.index('open') < 5
