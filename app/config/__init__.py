"""
app.config — centralized configuration package

Modules:
  Config          (re-exported from app/config.py)   — DB / JWT / SMTP settings
  FeatureFlags    (from feature_flags.py)             — runtime feature toggles
  TerminologyConfig (from terminology.py)             — enterprise label management

Backward compatibility:
  All existing `from app.config import Config` imports continue to work
  because Config is re-exported here from the sibling app/config.py file.
"""

# Re-export Config so that `from app.config import Config` keeps working
# after this directory became a package (previously resolved to app/config.py).
import importlib as _importlib
import sys as _sys
import os as _os

# Load the sibling config.py (which is now shadowed by this package directory)
_spec = _importlib.util.spec_from_file_location(
    "app._config_module",
    _os.path.join(_os.path.dirname(__file__), "..", "config.py"),
)
_config_module = _importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config_module)

Config = _config_module.Config

__all__ = ["Config"]
