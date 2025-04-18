"""Load YAML source definitions from a directory and return validated SourceConfig models."""

from pathlib import Path
from typing import List, Union

import yaml

from .models import SourceConfig

# =================================================================================================
# SOURCE LOADER
# =================================================================================================

def load_sources(folder: Union[str, Path] = "sources") -> List[SourceConfig]:
    """Load YAML source definitions and validate them.

    Args:
        folder: Path to the directory containing `.yaml` source files.

    Returns:
        A list of validated `SourceConfig` instances.
    """
    path: Path = Path(folder)
    configs: List[SourceConfig] = []
    for file_path in path.glob("*.yaml"):
        raw = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        config = SourceConfig(**data)
        configs.append(config)
    return configs
