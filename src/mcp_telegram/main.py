#!/usr/bin/env python3
"""Entry point for the Telegram MCP server."""

import sys

from dotenv import load_dotenv

from .server import run


def main() -> None:
    load_dotenv()
    try:
        run()
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
