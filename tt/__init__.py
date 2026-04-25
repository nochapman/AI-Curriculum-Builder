try:
    from .agent import root_agent
except (ImportError, ModuleNotFoundError) as exc:
    if "google" not in str(exc):
        raise
    root_agent = None
