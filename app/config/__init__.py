# app/config/ package initializer
# Re-exports Config so that `from app.config import Config` keeps working
# after app/config/ became a package directory.
import sys, os
import importlib.util

# Load app/config.py (the file one level up) as a module and expose Config
_config_file = os.path.join(os.path.dirname(__file__), "..", "config.py")
_spec = importlib.util.spec_from_file_location("_app_config_file", _config_file)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Config = _mod.Config
