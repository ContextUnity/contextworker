---
description: How to add a new background agent to ContextWorker
---

# Add New Agent

## Overview

ContextWorker uses a registry pattern for agents. Each agent:
- Inherits from `BaseAgent`
- Implements `run()` method (sync or async)
- Is registered with `@register("name")` decorator

## Steps

1. Create agent file:
   ```bash
   touch src/contextworker/agents/my_agent.py
   ```

2. Implement agent class:
   ```python
   # src/contextworker/agents/my_agent.py
   """
   MyAgent - Description of what this agent does.
   """
   
   import asyncio
   import logging
   from ..registry import register, BaseAgent
   
   logger = logging.getLogger(__name__)
   
   
   @register("my_agent")
   class MyAgent(BaseAgent):
       """Agent description."""
       name = "my_agent"
       
       def __init__(self, config: dict = None):
           super().__init__(config)
           self.poll_interval = self.config.get("poll_interval", 60)
       
       async def run(self):
           """Main async loop."""
           logger.info(f"MyAgent starting")
           
           while self._running:
               try:
                   count = await self._process()
                   if count == 0:
                       await asyncio.sleep(self.poll_interval)
               except Exception as e:
                   logger.exception(f"Error: {e}")
                   await asyncio.sleep(self.poll_interval)
       
       async def _process(self) -> int:
           """Process one batch. Return number of items processed."""
           # TODO: Implement your logic
           return 0
   ```

3. Import in agents/__init__.py (optional, registry auto-loads):
   ```python
   from . import my_agent
   ```

4. Add config (if needed) in `config.py`:
   ```python
   class MyAgentConfig(BaseModel):
       poll_interval: int = 60ж
       # other settings...
   
   class WorkerConfig(BaseSettings):
       # ...existing...
       my_agent: MyAgentConfig = Field(default_factory=MyAgentConfig)
   ```

5. Update `__main__.py` to pass config:
   ```python
   if args.agent == "my_agent":
       agent_config = {
           "poll_interval": config.my_agent.poll_interval,
           # ...
       }
   ```

6. Add environment variables to `.env.example`:
   ```bash
   # Agent: MyAgent
   MY_AGENT_POLL_INTERVAL_SEC=60
   ```

7. Test:
   ```bash
   python -m contextworker --list  # Should show my_agent
   python -m contextworker --agent my_agent
   ```

## Conventions

- Agent name: lowercase with underscores
- File name: same as agent name
- Class name: PascalCase + Agent suffix
- Use async for I/O bound operations
- Log at INFO level for progress, DEBUG for details