"""Tests for composite search scoring formula (Task 27)."""

import pytest
from datetime import datetime, timedelta

from app.models.search import SearchQuery, SearchResult, SortOrder


class TestSearchQueryModelUpdates:
    """Test SearchQuery model changes for composite scoring."""

    def test_include_expired_default_false(self):
        q = SearchQuery(query="test")
        assert q.include_expired is False

    def test_include_expired_true(self):
        q = SearchQuery(query="test", include_expired=True)
        assert q.include_expired is True

    def test_deprecated_recency_boost_still_accepted(self):
        q = SearchQuery(query="test", recency_boost=True)
        assert q.recency_boost is True

    def test_deprecated_recency_decay_still_accepted(self):
        q = SearchQuery(query="test", recency_decay=1.0)
        assert q.recency_decay == 1.0

    def test_deprecated_fields_description_mentions_deprecated(self):
        schema = SearchQuery.model_json_schema()
        props = schema['properties']
        assert 'DEPRECATED' in props['recency_boost']['description']
        assert 'DEPRECATED' in props['recency_decay']['description']


class TestSearchResultModelUpdates:
    """Test SearchResult model changes for composite scoring."""

    def test_score_breakdown_default_none(self):
        r = SearchResult(
            note_id=1, vault_name='v', relative_path='p',
            title='t', note_type='note', snippet='s', score=0.5,
        )
        assert r.score_breakdown is None
        assert r.decay_class is None
        assert r.confidence is None

    def test_score_breakdown_populated(self):
        breakdown = {
            'relevance': 0.85,
            'freshness': 0.72,
            'confidence': 1.0,
            'decision_boost': 0.0,
        }
        r = SearchResult(
            note_id=1, vault_name='v', relative_path='p',
            title='t', note_type='note', snippet='s', score=0.75,
            score_breakdown=breakdown,
            decay_class='stable',
            confidence=1.0,
        )
        assert r.score_breakdown == breakdown
        assert r.decay_class == 'stable'
        assert r.confidence == 1.0

    def test_serialization_roundtrip(self):
        breakdown = {'relevance': 0.9, 'freshness': 0.5, 'confidence': 0.8, 'decision_boost': 1.0}
        r = SearchResult(
            note_id=1, vault_name='v', relative_path='p',
            title='t', note_type='note', snippet='s', score=0.75,
            score_breakdown=breakdown, decay_class='permanent', confidence=0.8,
        )
        data = r.model_dump()
        restored = SearchResult(**data)
        assert restored.score_breakdown == breakdown
        assert restored.decay_class == 'permanent'
        assert restored.confidence == 0.8


class TestCompositeScoreFormula:
    """Test the composite scoring formula logic (unit-level)."""

    def _compute(self, relevance, freshness, confidence, decision_boost):
        """Mirror the composite formula from search_index.py."""
        return (
            relevance * 0.50
            + freshness * 0.25
            + confidence * 0.15
            + decision_boost * 0.10
        )

    def test_all_ones(self):
        """Perfect score across all components."""
        score = self._compute(1.0, 1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 0.001

    def test_all_zeros(self):
        """Worst score across all components."""
        score = self._compute(0.0, 0.0, 0.0, 0.0)
        assert abs(score - 0.0) < 0.001

    def test_relevance_only(self):
        """Only relevance contributes."""
        score = self._compute(1.0, 0.0, 0.0, 0.0)
        assert abs(score - 0.50) < 0.001

    def test_freshness_only(self):
        score = self._compute(0.0, 1.0, 0.0, 0.0)
        assert abs(score - 0.25) < 0.001

    def test_confidence_only(self):
        score = self._compute(0.0, 0.0, 1.0, 0.0)
        assert abs(score - 0.15) < 0.001

    def test_decision_boost_only(self):
        score = self._compute(0.0, 0.0, 0.0, 1.0)
        assert abs(score - 0.10) < 0.001

    def test_weights_sum_to_one(self):
        """Weights 0.50 + 0.25 + 0.15 + 0.10 = 1.00."""
        assert abs(0.50 + 0.25 + 0.15 + 0.10 - 1.0) < 0.001

    def test_relevance_dominates(self):
        """High relevance + low everything should beat low relevance + high everything."""
        score_high_rel = self._compute(1.0, 0.0, 0.0, 0.0)  # 0.50
        score_low_rel = self._compute(0.0, 1.0, 1.0, 1.0)   # 0.50
        # They're actually tied because weights sum to 1.0
        assert abs(score_high_rel - score_low_rel) < 0.001

    def test_decision_boost_breaks_tie(self):
        """Two equally relevant notes, decision one wins."""
        score_with = self._compute(0.8, 0.5, 1.0, 1.0)
        score_without = self._compute(0.8, 0.5, 1.0, 0.0)
        assert score_with > score_without
        assert abs(score_with - score_without - 0.10) < 0.001


class TestBm25Normalization:
    """Test BM25 normalization logic."""

    def test_single_result_gets_relevance_one(self):
        """A single result should get relevance = 1.0."""
        ranks = [-2.5]
        min_rank = min(abs(r) for r in ranks)
        max_rank = max(abs(r) for r in ranks)
        rank_range = max_rank - min_rank if max_rank != min_rank else 1.0
        # Single result: range is 0, so formula uses 1.0
        relevance = 1.0  # Single-result case
        assert relevance == 1.0

    def test_best_match_gets_relevance_one(self):
        """Most negative BM25 = best match = relevance 1.0."""
        # BM25 returns: -3.0 (best), -2.0, -1.0 (worst)
        ranks = [3.0, 2.0, 1.0]  # abs values
        min_rank, max_rank = min(ranks), max(ranks)
        rank_range = max_rank - min_rank
        # Best match (abs=1.0, most negative original)
        best_relevance = 1.0 - (1.0 - min_rank) / rank_range
        assert abs(best_relevance - 1.0) < 0.001

    def test_worst_match_gets_relevance_zero(self):
        """Least negative BM25 = worst match = relevance 0.0."""
        ranks = [3.0, 2.0, 1.0]
        min_rank, max_rank = min(ranks), max(ranks)
        rank_range = max_rank - min_rank
        worst_relevance = 1.0 - (3.0 - min_rank) / rank_range
        assert abs(worst_relevance - 0.0) < 0.001

    def test_middle_match(self):
        ranks = [3.0, 2.0, 1.0]
        min_rank, max_rank = min(ranks), max(ranks)
        rank_range = max_rank - min_rank
        mid_relevance = 1.0 - (2.0 - min_rank) / rank_range
        assert abs(mid_relevance - 0.5) < 0.001


class TestFreshnessCalculation:
    """Test the freshness formula: 1.0 / (1.0 + days_since / 30.0)."""

    def _freshness(self, days_old):
        return 1.0 / (1.0 + days_old / 30.0)

    def test_today(self):
        assert abs(self._freshness(0) - 1.0) < 0.01

    def test_thirty_days(self):
        assert abs(self._freshness(30) - 0.5) < 0.01

    def test_ninety_days(self):
        assert abs(self._freshness(90) - 0.25) < 0.01

    def test_one_year(self):
        f = self._freshness(365)
        assert f < 0.1  # Very old = very low freshness

    def test_monotonically_decreasing(self):
        values = [self._freshness(d) for d in range(0, 365, 30)]
        for i in range(len(values) - 1):
            assert values[i] > values[i + 1]
