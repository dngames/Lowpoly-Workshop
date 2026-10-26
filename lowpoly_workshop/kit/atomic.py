"""Atomic output: a file is written beside its target under a temporary name and renamed over it
in one step, so an interrupted run leaves the previous file or the new one, never half of one.
(Blender's own .blend save already works this way.)"""

import json
import os
from contextlib import contextmanager


@contextmanager
def replacing(path):
    """A temporary path beside `path` (same extension) to write; once the block ends without an
    error it replaces `path`, otherwise it is removed."""
    folder, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    tmp = os.path.join(folder, f".{stem}.part-{os.getpid()}{ext}")
    try:
        yield tmp
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_json(path, data, **kw):
    """`json.dump` to `path`, atomically."""
    with replacing(path) as tmp:
        with open(tmp, "w") as f:
            json.dump(data, f, **kw)
            f.flush()
            os.fsync(f.fileno())
