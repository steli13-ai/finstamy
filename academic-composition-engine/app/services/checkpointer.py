from __future__ import annotations

import atexit
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


_CHECKPOINTER = None
_CHECKPOINTER_CTX = None


def get_checkpointer(db_path: str = "data/checkpoints/langgraph.sqlite"):
    global _CHECKPOINTER, _CHECKPOINTER_CTX
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _CHECKPOINTER_CTX = SqliteSaver.from_conn_string(str(path))
    _CHECKPOINTER = _CHECKPOINTER_CTX.__enter__()

    def _close_checkpointer():
        global _CHECKPOINTER_CTX, _CHECKPOINTER
        if _CHECKPOINTER_CTX is not None:
            _CHECKPOINTER_CTX.__exit__(None, None, None)
            _CHECKPOINTER_CTX = None
            _CHECKPOINTER = None

    atexit.register(_close_checkpointer)
    return _CHECKPOINTER
