"""DPDP-Audit pipeline (SPEC-04): six stages, with ablations A1-A5 as configuration switches.

Imports are lazy so that light users (e.g. the tagger training script, which needs only
pipeline.claims) do not load the retrieval stack.
"""
from .config import CONFIGS, Config, get_config

__all__ = ["CONFIGS", "Config", "get_config", "run_case"]


def __getattr__(name):
    if name == "run_case":
        from .run import run_case
        return run_case
    raise AttributeError(name)
