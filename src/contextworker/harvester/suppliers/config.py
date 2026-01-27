"""
Supplier configuration loader for Harvester.

Loads configs from PROJECT_DIR/harvester/config/ (or custom path).
This module should be used ONLY by Worker, not Commerce.
"""

import tomllib
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from functools import lru_cache
import os


class SourceConfig(BaseModel):
    """Configuration for a single data source within a supplier."""

    id: str
    type: str = "http"  # http, imap, scraper, api
    url: str = ""
    format: str = "xlsx"
    brands: list[str] = Field(default_factory=list)
    currency: str = "UAH"
    category_whitelist: dict[str, list[str]] = Field(default_factory=dict)
    category_blacklist: dict[str, list[str]] = Field(default_factory=dict)
    cleanup_files: bool = False


class SupplierConfig(BaseModel):
    """Configuration for a supplier/dealer."""

    name: str
    dealer_code: str
    sources: list[SourceConfig] = Field(default_factory=list)


class HarvesterSettings(BaseModel):
    """Global harvester settings."""

    import_dir: str = "import"
    processed_dir: str = "import/processed_payload"
    max_file_size_mb: int = 50
    download_timeout_seconds: int = 30
    cleanup_files: bool = False


def get_project_dir() -> Path:
    """Get project directory from environment.
    
    Uses PROJECT_DIR env var, falling back to current directory.
    """
    project_dir = os.getenv("PROJECT_DIR")
    if project_dir:
        return Path(project_dir)

    # Default: current working directory
    return Path.cwd()


def find_config_dir() -> Path:
    """Find the harvester config directory.
    
    Looks in order:
    1. HARVESTER_CONFIG_DIR env var
    2. {PROJECT_DIR}/harvester/config
    """
    # 1. Explicit environment variable
    if env_dir := os.getenv("HARVESTER_CONFIG_DIR"):
        p = Path(env_dir)
        if p.exists():
            return p

    # 2. Project directory config
    project_dir = get_project_dir()
    config_dir = project_dir / "harvester" / "config"
    if config_dir.exists():
        return config_dir

    raise FileNotFoundError(
        "Harvester config directory not found. "
        "Set PROJECT_DIR or HARVESTER_CONFIG_DIR"
    )


@lru_cache(maxsize=1)
def load_settings(config_dir: Path | None = None) -> HarvesterSettings:
    """Load global harvester settings."""
    if config_dir is None:
        config_dir = find_config_dir()

    settings_file = config_dir / "settings.toml"
    if not settings_file.exists():
        return HarvesterSettings()

    with open(settings_file, "rb") as f:
        data = tomllib.load(f)

    return HarvesterSettings(
        import_dir=data.get("paths", {}).get("import_dir", "import"),
        processed_dir=data.get("paths", {}).get(
            "processed_dir", "import/processed_payload"
        ),
        max_file_size_mb=data.get("fetching", {}).get("max_file_size_mb", 50),
        download_timeout_seconds=data.get("fetching", {}).get(
            "download_timeout_seconds", 30
        ),
        cleanup_files=data.get("fetching", {}).get("cleanup_files", False),
    )


def load_supplier_config(
    supplier_code: str, config_dir: Path | None = None
) -> SupplierConfig:
    """Load configuration for a specific supplier."""
    if config_dir is None:
        config_dir = find_config_dir()

    supplier_file = config_dir / "suppliers" / f"{supplier_code}.toml"
    if not supplier_file.exists():
        raise FileNotFoundError(f"Supplier config not found: {supplier_file}")

    with open(supplier_file, "rb") as f:
        data = tomllib.load(f)

    supplier_data = data.get("supplier", {})
    sources = []

    for src in supplier_data.get("sources", []):
        sources.append(
            SourceConfig(
                id=src.get("id", "default"),
                type=src.get("type", "http"),
                url=src.get("url", ""),
                format=src.get("format", "xlsx"),
                brands=src.get("brands", []),
                currency=src.get("currency", "UAH"),
                category_whitelist=src.get("category_whitelist", {}),
                category_blacklist=src.get("category_blacklist", {}),
                cleanup_files=src.get("cleanup_files", False),
            )
        )

    return SupplierConfig(
        name=supplier_data.get("name", supplier_code),
        dealer_code=supplier_data.get("dealer_code", supplier_code),
        sources=sources,
    )


def load_all_suppliers(config_dir: Path | None = None) -> dict[str, SupplierConfig]:
    """Load all supplier configurations."""
    if config_dir is None:
        config_dir = find_config_dir()

    suppliers_dir = config_dir / "suppliers"
    if not suppliers_dir.exists():
        return {}

    suppliers = {}
    for toml_file in suppliers_dir.glob("*.toml"):
        supplier_code = toml_file.stem
        try:
            suppliers[supplier_code] = load_supplier_config(supplier_code, config_dir)
        except Exception as e:
            print(f"Warning: Failed to load {supplier_code}: {e}")

    return suppliers


def load_brands_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Load brand-country mappings."""
    if config_dir is None:
        config_dir = find_config_dir()

    brands_file = config_dir / "brands.toml"
    if not brands_file.exists():
        return {}

    with open(brands_file, "rb") as f:
        return tomllib.load(f)
