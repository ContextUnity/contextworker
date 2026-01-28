"""
Tests for Agent Registry.
"""

import pytest
from contextworker.registry import (
    register,
    get_agent,
    list_agents,
    BaseAgent,
    _agents,
)


class TestRegisterDecorator:
    """Test @register decorator."""

    def test_register_adds_agent_to_registry(self):
        """Verify register() adds agent class to registry."""
        # Clear any existing test agents
        test_name = "test_agent_decorator"
        if test_name in _agents:
            del _agents[test_name]

        @register(test_name)
        class TestAgent(BaseAgent):
            name = test_name

        assert test_name in _agents
        assert _agents[test_name] == TestAgent

        # Cleanup
        del _agents[test_name]

    def test_register_returns_original_class(self):
        """Verify decorator returns the class unchanged."""
        test_name = "test_agent_return"
        if test_name in _agents:
            del _agents[test_name]

        @register(test_name)
        class TestAgent(BaseAgent):
            name = test_name

        # The decorated class should work normally
        agent = TestAgent()
        assert agent.name == test_name

        # Cleanup
        del _agents[test_name]


class TestGetAgent:
    """Test get_agent() function."""

    def test_get_agent_returns_class(self):
        """Verify get_agent returns registered agent class."""
        test_name = "test_get_agent"
        if test_name in _agents:
            del _agents[test_name]

        @register(test_name)
        class TestAgent(BaseAgent):
            name = test_name

        result = get_agent(test_name)
        assert result == TestAgent

        # Cleanup
        del _agents[test_name]

    def test_get_agent_raises_for_unknown(self):
        """Verify get_agent raises ValueError for unknown agent."""
        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent("nonexistent_agent_xyz")


class TestListAgents:
    """Test list_agents() function."""

    def test_list_agents_returns_list(self):
        """Verify list_agents returns a list of names."""
        result = list_agents()
        assert isinstance(result, list)

    def test_list_agents_includes_registered(self):
        """Verify registered agents appear in list."""
        test_name = "test_list_agent"
        if test_name in _agents:
            del _agents[test_name]

        @register(test_name)
        class TestAgent(BaseAgent):
            name = test_name

        result = list_agents()
        assert test_name in result

        # Cleanup
        del _agents[test_name]


class TestBaseAgent:
    """Test BaseAgent base class."""

    def test_base_agent_default_name(self):
        """Verify BaseAgent has default name."""
        agent = BaseAgent()
        assert agent.name == "base"

    def test_base_agent_accepts_config(self):
        """Verify BaseAgent stores config."""
        config = {"key": "value", "batch_size": 100}
        agent = BaseAgent(config=config)
        assert agent.config == config

    def test_base_agent_empty_config_default(self):
        """Verify BaseAgent defaults to empty config."""
        agent = BaseAgent()
        assert agent.config == {}

    def test_base_agent_running_flag(self):
        """Verify BaseAgent has _running flag."""
        agent = BaseAgent()
        assert agent._running is False

    def test_base_agent_stop_sets_flag(self):
        """Verify stop() sets _running to False."""
        agent = BaseAgent()
        agent._running = True
        agent.stop()
        assert agent._running is False

    def test_base_agent_run_raises_not_implemented(self):
        """Verify run() raises NotImplementedError."""
        agent = BaseAgent()
        with pytest.raises(NotImplementedError):
            agent.run()


class TestCustomAgent:
    """Test custom agent implementation."""

    def test_custom_agent_can_override_run(self):
        """Verify custom agent can implement run()."""

        class MyAgent(BaseAgent):
            name = "my_agent"
            ran = False

            def run(self):
                self.ran = True

        agent = MyAgent()
        agent.run()
        assert agent.ran is True

    def test_custom_agent_can_override_name(self):
        """Verify custom agent can set custom name."""

        class CustomNameAgent(BaseAgent):
            name = "custom_name"

        agent = CustomNameAgent()
        assert agent.name == "custom_name"
