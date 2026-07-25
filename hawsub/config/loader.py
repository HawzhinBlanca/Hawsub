import os
import yaml
from pathlib import Path
from typing import Union, Optional
from hawsub.config.schema import HawsubConfig


def load_config(config_path: Optional[Union[str, Path]] = None) -> HawsubConfig:
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return HawsubConfig(**data)
    
    # Check default config locations
    default_locations = [
        Path("config/hawsub.yaml"),
        Path("config/hawsub.yml"),
        Path("hawsub.yaml"),
    ]
    for loc in default_locations:
        if loc.exists():
            with open(loc, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return HawsubConfig(**data)
    
    return HawsubConfig()
