"""Tests for worker schedule payload conversion."""

import pytest
from contextunity.worker.schedules import schedule_config_from_wire


class TestScheduleConfig:
    """Verify schedule dictionaries are converted at the RPC/manifest boundary."""

    def test_from_wire_accepts_valid_schedule(self):
        config = schedule_config_from_wire(
            {
                "schedule_id": "test-schedule",
                "workflow_name": "TestWorkflow",
                "task_queue": "test-tasks",
                "cron": "0 0 * * *",
                "args": [{"tenant_id": "tenant-a"}],
                "description": "nightly run",
            }
        )
        assert config.schedule_id == "test-schedule"
        assert config.workflow_name == "TestWorkflow"
        assert config.task_queue == "test-tasks"
        assert config.cron == "0 0 * * *"
        assert config.args == [{"tenant_id": "tenant-a"}]
        assert config.description == "nightly run"

    @pytest.mark.parametrize("missing_key", ["schedule_id", "workflow_name", "task_queue", "cron"])
    def test_from_wire_rejects_missing_required_fields(self, missing_key: str):
        payload: dict[str, object] = {
            "schedule_id": "test-schedule",
            "workflow_name": "TestWorkflow",
            "task_queue": "test-tasks",
            "cron": "0 0 * * *",
        }
        payload.pop(missing_key)

        with pytest.raises(ValueError, match=missing_key):
            schedule_config_from_wire(payload)

    def test_from_wire_ignores_non_list_args_and_non_string_description(self):
        config = schedule_config_from_wire(
            {
                "schedule_id": "test-schedule",
                "workflow_name": "TestWorkflow",
                "task_queue": "test-tasks",
                "cron": "0 0 * * *",
                "args": "not-a-list",
                "description": 123,
            }
        )
        assert config.args is None
        assert config.description == ""
