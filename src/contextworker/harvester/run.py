"""
Harvester CLI - Run product import for a project.

Usage:
    python -m contextworker.harvester.run --project traverse
    python -m contextworker.harvester.run --project traverse --supplier vysota
    python -m contextworker.harvester.run  # Uses DEFAULT_PROJECT from .env

Environment Variables:
    PROJECTS_DIR - Absolute path to projects directory
    DEFAULT_PROJECT - Project to use if --project not specified
    BRAIN_GRPC_URL - Brain gRPC endpoint for DB operations
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load worker .env first
load_dotenv()

logger = logging.getLogger(__name__)


def get_project_dir(project_name: str) -> Path:
    """Get absolute path to project directory.

    Looks for project in PROJECTS_DIR environment variable.
    """
    projects_dir = os.getenv("PROJECTS_DIR")
    if not projects_dir:
        raise ValueError(
            "PROJECTS_DIR environment variable not set. "
            "Set it to the absolute path containing your projects (e.g., /home/user/projects)"
        )

    project_dir = Path(projects_dir) / project_name
    if not project_dir.exists():
        raise ValueError(f"Project directory not found: {project_dir}")

    return project_dir


def setup_project(project_dir: Path) -> dict:
    """Setup project environment and return config.

    1. Load project .env
    2. Add project/harvester to Python path
    3. Return project config
    """
    # Load project-specific .env (overrides worker .env)
    project_env = project_dir / ".env"
    if project_env.exists():
        load_dotenv(project_env, override=True)

    # Add project/harvester to path for importing fetchers/transformers
    harvester_path = project_dir / "harvester"
    if harvester_path.exists() and str(harvester_path) not in sys.path:
        sys.path.insert(0, str(harvester_path))
        logger.info(f"Added to Python path: {harvester_path}")

    # Load project config
    config_file = project_dir / "config.toml"
    config = {}
    if config_file.exists():
        import tomllib

        with open(config_file, "rb") as f:
            config = tomllib.load(f)

    return config


async def run_harvest(project_name: str, supplier: str = None) -> dict:
    """Run harvest for a project.

    Args:
        project_name: Project directory name
        supplier: Specific supplier to run, or None for all

    Returns:
        Results dict with success/failure counts
    """
    from contextworker.harvester import HarvestOrchestrator

    project_dir = get_project_dir(project_name)
    config = setup_project(project_dir)

    brain_url = os.getenv("BRAIN_GRPC_URL", "localhost:50051")
    tenant_id = os.getenv(
        "TENANT_ID", config.get("project", {}).get("tenant_id", project_name)
    )

    logger.info(
        f"Starting harvest for project={project_name} supplier={supplier or 'all'}"
    )

    orchestrator = HarvestOrchestrator(
        supplier_code=supplier or "all",
        brain_url=brain_url,
        tenant_id=tenant_id,
    )

    return await orchestrator.run()


def main():
    parser = argparse.ArgumentParser(
        description="Run product harvest for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project",
        "-p",
        default=os.getenv("DEFAULT_PROJECT"),
        help="Project name (default: DEFAULT_PROJECT env var)",
    )
    parser.add_argument(
        "--supplier", "-s", help="Specific supplier to run (default: all)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Validate project
    if not args.project:
        parser.error(
            "Project not specified. Use --project or set DEFAULT_PROJECT in .env"
        )

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Run async
    try:
        result = asyncio.run(run_harvest(args.project, args.supplier))
        logger.info(f"Harvest complete: {result}")
    except KeyboardInterrupt:
        logger.info("Harvest interrupted")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Harvest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
