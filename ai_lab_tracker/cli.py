"""Console script entry point for the ai_lab_tracker CLI."""

import asyncio
import logging
import os
from pathlib import Path
from rich.logging import RichHandler

from .tracker import run_once

# Load environment variables from .env if present
env_path = Path('.env')
if env_path.exists():
    with env_path.open('r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

def main() -> None:
    """Console script entrypoint."""
    # Configure Rich logging handler for colorful console output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True)]
    )
    asyncio.run(run_once())

if __name__ == "__main__":
    main()
