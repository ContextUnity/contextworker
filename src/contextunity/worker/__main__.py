"""contextunity.worker — unified entry point."""

from __future__ import annotations

import sys

from .cli import app


def main():
    """Run the Worker CLI application."""
    app(sys.argv[1:])


if __name__ == "__main__":
    main()
