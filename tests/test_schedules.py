"""
Tests for ScheduleConfig and scheduling utilities.
"""

from contextworker.schedules import DEFAULT_SCHEDULES, ScheduleConfig


class TestScheduleConfig:
    """Test ScheduleConfig dataclass."""

    def test_schedule_config_creation(self):
        """Test creating a schedule config with required fields."""
        config = ScheduleConfig(
            schedule_id="test-schedule",
            workflow_name="TestWorkflow",
            workflow_class=None,
            task_queue="test-tasks",
            cron="0 0 * * *",
        )

        assert config.schedule_id == "test-schedule"
        assert config.workflow_name == "TestWorkflow"
        assert config.task_queue == "test-tasks"
        assert config.cron == "0 0 * * *"
        assert config.args is None
        assert config.description == ""

    def test_schedule_config_with_optional_fields(self):
        """Test creating a schedule config with all fields."""
        config = ScheduleConfig(
            schedule_id="test-schedule",
            workflow_name="TestWorkflow",
            workflow_class=None,
            task_queue="test-tasks",
            cron="*/5 * * * *",
            args=["arg1", "arg2"],
            description="Test description",
        )

        assert config.args == ["arg1", "arg2"]
        assert config.description == "Test description"


class TestDefaultSchedules:
    """Test DEFAULT_SCHEDULES configuration."""

    def test_default_schedules_exist(self):
        """Verify default schedules are defined."""
        assert len(DEFAULT_SCHEDULES) >= 2

    def test_harvester_schedule_exists(self):
        """Verify harvester schedule is defined."""
        harvester = next((s for s in DEFAULT_SCHEDULES if s.schedule_id == "harvester-daily"), None)
        assert harvester is not None
        assert harvester.workflow_name == "HarvestWorkflow"
        assert harvester.task_queue == "harvest-tasks"

    def test_gardener_schedule_exists(self):
        """Verify gardener schedule is defined."""
        gardener = next(
            (s for s in DEFAULT_SCHEDULES if s.schedule_id == "gardener-every-5min"),
            None,
        )
        assert gardener is not None
        assert gardener.workflow_name == "GardenerWorkflow"
        assert gardener.task_queue == "gardener-tasks"
        assert gardener.cron == "*/5 * * * *"

    def test_all_schedules_have_valid_cron(self):
        """Verify all schedules have valid cron expressions."""
        for schedule in DEFAULT_SCHEDULES:
            assert schedule.cron is not None
            assert len(schedule.cron.split()) == 5, f"Invalid cron: {schedule.cron}"
