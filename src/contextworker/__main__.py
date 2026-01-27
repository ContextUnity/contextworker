"""
ContextWorker CLI entry point.

Usage:
    python -m contextworker --agent gardener
    python -m contextworker --list
    python -m contextworker --all
"""

import argparse
import logging
import sys

from contextcore import setup_logging, load_shared_config_from_env

from .config import WorkerConfig
from .registry import get_agent, list_agents


def main():
    parser = argparse.ArgumentParser(description="ContextWorker Agent Runner")
    parser.add_argument("--agent", type=str, help="Agent name to run (e.g., gardener)")
    parser.add_argument("--list", action="store_true", help="List available agents")
    parser.add_argument(
        "--all", action="store_true", help="Run all agents (not recommended)"
    )

    args = parser.parse_args()

    # Setup logging
    try:
        core_config = load_shared_config_from_env()
        setup_logging(config=core_config, service_name="contextworker")
    except Exception:
        logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger(__name__)

    if args.list:
        print("Available agents:")
        for name in list_agents():
            print(f"  - {name}")
        return

    if not args.agent and not args.all:
        parser.print_help()
        sys.exit(1)

    # Load worker config
    config = WorkerConfig.from_env()

    if args.agent:
        agent_cls = get_agent(args.agent)

        # Get agent-specific config
        agent_config = {}
        if args.agent == "gardener":
            agent_config = {
                "poll_interval": config.gardener.poll_interval,
                "batch_size": config.gardener.batch_size,
                "parallel_batches": config.gardener.parallel_batches,
                "llm_timeout": config.gardener.llm_timeout,
                "retry_max": config.gardener.retry_max,
                "retry_base_delay": config.gardener.retry_base_delay,
                "brain_db_url": config.brain_database_url,
                "commerce_db_url": config.commerce_database_url,
                "router_url": config.router_url,
                "router_model": config.router_model,
                "router_api_key": config.router_api_key,
            }

        agent = agent_cls(config=agent_config)
        agent.start()

    elif args.all:
        logger.warning(
            "Running all agents in single process is not recommended for production"
        )
        # TODO: Implement multiprocessing or threading for all agents
        raise NotImplementedError("Use --agent <name> to run specific agent")


if __name__ == "__main__":
    main()
