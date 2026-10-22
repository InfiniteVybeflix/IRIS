"""IRIS Runtime Singleton — holds the global IRIS core instance.

This exists so that any module (autonomous_loop, etc.) can access the
running IRIS instance without circular imports. `app.py` calls
`set_iris_core(iris)` after `IRISCore()` initializes.
"""

_iris_core = None


def set_iris_core(core):
    """Called by app.py at startup to register the IRIS singleton."""
    global _iris_core
    _iris_core = core


def get_iris_core():
    """Get the running IRIS instance, or None if not yet booted."""
    return _iris_core


def get_omnis():
    """Shortcut: get the OMNIS agent instance, or None."""
    if _iris_core is None:
        return None
    return getattr(_iris_core, "omnis", None)
