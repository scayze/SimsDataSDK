"""Exception hierarchy shared by every ``sims4_sdk`` module.

Every SDK-specific error derives from :class:`Sims4SDKError`, so callers can
guard a whole integration with one ``except`` clause::

    from sims4_sdk import Sims4SDKError

    try:
        save = workspace.read_save(path)
    except Sims4SDKError:
        ...

The concrete errors also keep their historical builtin base classes
(``ValueError`` for malformed data, ``RuntimeError`` for the wiki client), so
existing ``except ValueError:`` handlers keep working.
"""

from __future__ import annotations

__all__ = ["Sims4SDKError"]


class Sims4SDKError(Exception):
    """Base class for every error raised by ``sims4_sdk``."""
