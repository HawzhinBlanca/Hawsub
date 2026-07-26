import os
import yaml
from pathlib import Path
from typing import Union, Optional
from hawsub.config.schema import HawsubConfig
import logging

logger = logging.getLogger("hawsub.config")


def load_config(config_path: Optional[Union[str, Path]] = None) -> HawsubConfig:
    """Load Hawsub configuration from YAML file with error handling.
    
    Falls back to default config if the file is missing, malformed, or contains
    invalid values. Never crashes — always returns a valid HawsubConfig.
    """
    if config_path and Path(config_path).exists():
        return _safe_load_yaml(Path(config_path))
    
    # Check default config locations
    default_locations = [
        Path("config/hawsub.yaml"),
        Path("config/hawsub.yml"),
        Path("hawsub.yaml"),
    ]
    for loc in default_locations:
        if loc.exists():
            return _safe_load_yaml(loc)
    
    return HawsubConfig()


def _safe_load_yaml(path: Path) -> HawsubConfig:
    """Safely load and validate a YAML config file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if data is None:
            logger.warning(f"Config file {path} is empty, using defaults")
            return HawsubConfig()
        
        if not isinstance(data, dict):
            logger.warning(f"Config file {path} does not contain a dict, using defaults")
            return HawsubConfig()
        
        return HawsubConfig(**data)
    
    except yaml.YAMLError as e:
        logger.error(f"Malformed YAML in {path}: {e}. Using default config.")
        return HawsubConfig()
    except Exception as e:
        logger.error(f"Error loading config from {path}: {e}. Using default config.")
        return HawsubConfig()
