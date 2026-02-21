"""Tests for retention job logic."""

from __future__ import annotations

from contextworker.jobs.retention import _extract_facts_simple


class TestExtractFactsSimple:
    """Test the heuristic fact extraction."""

    def test_extracts_interaction_count(self):
        episodes = [
            {"id": "1", "content": "Hello", "created_at": "2026-01-01"},
            {"id": "2", "content": "World", "created_at": "2026-01-02"},
        ]
        facts = _extract_facts_simple(episodes)
        assert facts["total_interactions"] == "2"

    def test_extracts_date_range(self):
        episodes = [
            {"id": "1", "content": "A", "created_at": "2026-01-10"},
            {"id": "2", "content": "B", "created_at": "2026-01-01"},
            {"id": "3", "content": "C", "created_at": "2026-01-20"},
        ]
        facts = _extract_facts_simple(episodes)
        assert facts["first_interaction"] == "2026-01-01"
        assert facts["last_interaction"] == "2026-01-20"

    def test_extracts_session_count(self):
        episodes = [
            {"id": "1", "content": "A", "metadata": {"session_id": "s1"}},
            {"id": "2", "content": "B", "metadata": {"session_id": "s1"}},
            {"id": "3", "content": "C", "metadata": {"session_id": "s2"}},
        ]
        facts = _extract_facts_simple(episodes)
        assert facts["session_count"] == "2"

    def test_handles_empty_episodes(self):
        facts = _extract_facts_simple([])
        assert facts["total_interactions"] == "0"

    def test_handles_missing_metadata(self):
        episodes = [
            {"id": "1", "content": "A"},
            {"id": "2", "content": "B", "metadata": {}},
        ]
        facts = _extract_facts_simple(episodes)
        assert "session_count" not in facts

    def test_handles_missing_dates(self):
        episodes = [
            {"id": "1", "content": "A"},
            {"id": "2", "content": "B"},
        ]
        facts = _extract_facts_simple(episodes)
        assert "first_interaction" not in facts


class TestRetentionSchedule:
    """Test retention appears in default schedules."""

    def test_retention_schedule_exists(self):
        from contextworker.schedules import DEFAULT_SCHEDULES

        retention = [s for s in DEFAULT_SCHEDULES if "retention" in s.schedule_id]
        assert len(retention) == 1
        assert retention[0].cron == "0 3 * * *"
        assert retention[0].task_queue == "retention-tasks"
